"""Transactional application state and public event log."""

import contextvars
import hashlib
import sqlite3
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from trl.contracts import (
    Clarify,
    CreateRun,
    Disrupt,
    Event,
    EventDraft,
    IncidentView,
    Metrics,
    ModelCall,
    Receipt,
    Retract,
    Retry,
    RunBody,
    RunView,
    incident_id,
)
from trl.domain import Offer, Record, Scenario, Vote
from trl.lifecycle import IllegalTransition, check_command, check_worker_transition, retryable
from trl.migrations import migrate
from trl.robustness import PROFILE, snapshot_id
from trl.settings import get_settings
from trl.vnext import OperatorMode, RunEvidence

VNEXT_FIELDS = {
    "workflow",
    "operator_mode",
    "route_policy",
    "preference_a",
    "preference_b",
    "evidence",
    "clarification_option",
}

EVENT_DRAFT = TypeAdapter(EventDraft)


class NotFound(LookupError):
    """Unknown run identifier."""


class Conflict(ValueError):
    """The command conflicts with current state or a prior request."""


class Fenced(RuntimeError):
    """The writer's lease was revoked or expired. Its write was refused."""


@dataclass(frozen=True)
class Fence:
    """Proof that a worker holds the execution lease for one run."""

    run_id: str
    token: int


# Workers set this once; every guarded write checks it in the writing transaction.
current_fence: contextvars.ContextVar[Fence | None] = contextvars.ContextVar(
    "current_fence", default=None
)


class RunStore:
    def __init__(
        self,
        path: Path,
        *,
        lease_ttl: float | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.path = path.resolve()
        self.checkpoint_path = self.path.with_name(f"{self.path.stem}.checkpoints.sqlite")
        self.lease_ttl = lease_ttl if lease_ttl is not None else get_settings().lease_ttl
        self.clock = clock
        self.subscribers: list[Callable[[], None]] = []
        path.parent.mkdir(parents=True, exist_ok=True)
        migrate(self.path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def acquire_lease(self, run_id: str, version: int, owner: str) -> Fence | None:
        """Take the execution lease unless another live worker holds it for this revision."""
        now = self.clock()
        with self.write() as connection:
            run = self._read(connection, run_id)
            if run.version != version or run.status != "planning":
                return None
            row = connection.execute(
                "SELECT version, owner, token, expires_at FROM leases WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                token = 1
                connection.execute(
                    "INSERT INTO leases (run_id, version, owner, token, expires_at) "
                    "VALUES (?,?,?,?,?)",
                    (run_id, version, owner, token, now + self.lease_ttl),
                )
                return Fence(run_id, token)
            held = row["owner"] is not None and row["expires_at"] > now
            if held and row["owner"] != owner and row["version"] == version:
                return None
            token = row["token"] + 1
            connection.execute(
                "UPDATE leases SET version=?, owner=?, token=?, expires_at=? WHERE run_id=?",
                (version, owner, token, now + self.lease_ttl, run_id),
            )
            return Fence(run_id, token)

    def heartbeat(self, fence: Fence) -> bool:
        with self.write() as connection:
            return (
                connection.execute(
                    "UPDATE leases SET expires_at=? WHERE run_id=? AND token=?",
                    (self.clock() + self.lease_ttl, fence.run_id, fence.token),
                ).rowcount
                == 1
            )

    def release_lease(self, fence: Fence) -> None:
        with self.write() as connection:
            connection.execute(
                "UPDATE leases SET owner=NULL, expires_at=0 WHERE run_id=? AND token=?",
                (fence.run_id, fence.token),
            )

    @staticmethod
    def _require_fence(connection: sqlite3.Connection, run_id: str) -> None:
        fence = current_fence.get()
        if fence is None or fence.run_id != run_id:
            return
        row = connection.execute("SELECT token FROM leases WHERE run_id=?", (run_id,)).fetchone()
        if row is None or row["token"] != fence.token:
            raise Fenced("The execution lease was revoked.")

    @staticmethod
    def _revoke(connection: sqlite3.Connection, run_id: str) -> None:
        """A command makes any running worker stale by moving the token on."""
        connection.execute(
            "UPDATE leases SET token=token+1, owner=NULL, expires_at=0 WHERE run_id=?", (run_id,)
        )

    @contextmanager
    def write(self) -> Generator[sqlite3.Connection]:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
        for notify in self.subscribers:
            notify()

    @staticmethod
    def _read(connection: sqlite3.Connection, run_id: str) -> RunBody:
        row = connection.execute("SELECT body FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise NotFound("The run does not exist.")
        return RunBody.model_validate_json(row["body"])

    def read(self, run_id: str) -> RunBody:
        with closing(self.connect()) as connection:
            return self._read(connection, run_id)

    def active(self) -> list[Receipt]:
        with closing(self.connect()) as connection:
            return [
                Receipt(run_id=row["id"], version=row["version"])
                for row in connection.execute(
                    "SELECT id, version FROM runs WHERE status='planning'"
                )
            ]

    def view(self, run_id: str) -> RunView:
        with closing(self.connect()) as connection:
            connection.execute("BEGIN")
            run = self._read(connection, run_id)
            params = (run.id, run.version)
            offers = tuple(
                Offer.model_validate_json(row["body"])
                for row in connection.execute(
                    "SELECT body FROM offers WHERE run_id=? AND version=? ORDER BY ordinal",
                    params,
                )
            )
            votes = tuple(
                Vote.model_validate_json(row["body"])
                for row in connection.execute(
                    "SELECT body FROM votes WHERE run_id=? AND version=? ORDER BY offer_id, rider",
                    params,
                )
            )
            metrics = connection.execute(
                """SELECT CASE WHEN count(*) = 0 THEN 'none'
                               WHEN min(model) = 'replay' THEN 'replay' ELSE 'ollama'
                          END backend,
                          count(*) calls, coalesce(sum(input_tokens),0) input_tokens,
                          coalesce(sum(output_tokens),0) output_tokens,
                          coalesce(sum(duration_ms),0) model_ms
                   FROM model_calls WHERE run_id=? AND version=?""",
                params,
            ).fetchone()
        return RunView(
            id=run.id,
            version=run.version,
            status=run.status,
            architecture=run.architecture,
            service_date=run.scenario.service_date.isoformat(),
            scenario=run.scenario.id,
            notice=run.scenario.notice,
            origin_a=run.scenario.a.stop,
            origin_b=run.scenario.b.stop,
            destinations=run.scenario.destinations,
            initial=run.initial,
            incident=run.incident,
            offers=offers,
            votes=votes,
            question=run.question,
            verified_offer=run.verified_offer,
            error=run.error,
            retryable=retryable(run.status, run.error),
            incidents=tuple(
                IncidentView(id=incident_id(item), disruption=item) for item in run.overlays
            ),
            metrics=Metrics.model_validate(dict(metrics)),
            **(
                {
                    "evidence": run.evidence.model_copy(
                        update={
                            "notice_text": run.notice,
                            "answer_text": run.clarification
                            if run.clarification_option is None
                            else None,
                        }
                    )
                }
                if run.evidence is not None
                else {}
            ),
        )

    def events(self, run_id: str, after: int, limit: int = 128) -> list[Event]:
        with closing(self.connect()) as connection:
            return [
                Event(
                    seq=row["seq"],
                    version=row["version"],
                    recorded_at=row["recorded_at"],
                    **EVENT_DRAFT.validate_json(row["body"]).model_dump(),
                )
                for row in connection.execute(
                    """SELECT seq, version, recorded_at, body FROM events
                       WHERE run_id=? AND seq>? ORDER BY seq LIMIT ?""",
                    (run_id, after, limit),
                )
            ]

    @staticmethod
    def _get_command(
        connection: sqlite3.Connection,
        scope: str,
        key: str,
        request: Record,
    ) -> tuple[str, Receipt | None]:
        excluded: set[str] = set()
        if isinstance(request, CreateRun) and request.workflow == "legacy":
            excluded = VNEXT_FIELDS
        elif isinstance(request, Clarify) and request.question_id is None:
            excluded = {"question_id", "option_id"}
        elif isinstance(request, Disrupt) and request.mode == "add":
            excluded = {"mode"}
        digest = hashlib.sha256(request.model_dump_json(exclude=excluded).encode()).hexdigest()
        row = connection.execute(
            "SELECT fingerprint, response FROM commands WHERE scope=? AND key=?",
            (scope, key),
        ).fetchone()
        if row is None:
            return digest, None
        if row["fingerprint"] != digest:
            raise Conflict("This idempotency key already belongs to a different request.")
        return digest, Receipt.model_validate_json(row["response"])

    @staticmethod
    def _save_command(
        connection: sqlite3.Connection,
        scope: str,
        key: str,
        digest: str,
        receipt: Receipt,
    ) -> Receipt:
        connection.execute(
            "INSERT INTO commands VALUES (?,?,?,?)", (scope, key, digest, receipt.model_dump_json())
        )
        return receipt

    @staticmethod
    def _event(connection: sqlite3.Connection, run: RunBody, event: EventDraft) -> None:
        connection.execute(
            "INSERT INTO events (run_id, version, body) VALUES (?,?,?)",
            (run.id, run.version, event.model_dump_json()),
        )

    @staticmethod
    def _update(connection: sqlite3.Connection, run: RunBody) -> None:
        connection.execute(
            "UPDATE runs SET version=?, status=?, body=? WHERE id=?",
            (run.version, run.status, RunStore.encode_run(run), run.id),
        )

    @staticmethod
    def encode_run(run: RunBody) -> str:
        return run.model_dump_json(exclude=VNEXT_FIELDS if run.workflow == "legacy" else set())

    def create(
        self,
        request: CreateRun,
        key: str,
        scenario: Scenario,
        initial: Offer | None,
        *,
        default_operator: OperatorMode = "rules",
        initial_complete: bool = True,
    ) -> Receipt:
        with self.write() as connection:
            digest, previous = self._get_command(connection, "create", key, request)
            if previous:
                return previous
            operator_mode = request.operator_mode or default_operator
            run = RunBody(
                id=uuid4().hex,
                status="ready" if initial_complete else "search_incomplete",
                architecture=request.architecture,
                counteroffers=request.counteroffers,
                scenario=scenario,
                initial=initial,
                workflow=request.workflow,
                operator_mode=operator_mode,
                route_policy=request.route_policy,
                preference_a=request.preference_a,
                preference_b=request.preference_b,
                evidence=RunEvidence(
                    snapshot=snapshot_id(scenario),
                    scenario_profile=PROFILE,
                    operator_mode=operator_mode,
                )
                if request.workflow == "vnext"
                else None,
            )
            connection.execute(
                "INSERT INTO runs VALUES (?,?,?,?)",
                (run.id, run.version, run.status, self.encode_run(run)),
            )
            self._event(
                connection,
                run,
                EventDraft(
                    kind="ready",
                    role="system",
                    message="The initial timetable is ready."
                    if initial_complete
                    else "The initial route search exhausted its budget.",
                ),
            )
            return self._save_command(
                connection, "create", key, digest, Receipt(run_id=run.id, version=run.version)
            )

    def command(
        self, run_id: str, key: str, request: Disrupt | Clarify | Retract | Retry
    ) -> Receipt:
        scope = f"{type(request).__name__}:{run_id}"
        with self.write() as connection:
            digest, previous = self._get_command(connection, scope, key, request)
            if previous:
                return previous
            run = self._read(connection, run_id)
            if request.version != run.version:
                raise Conflict("The run has a newer incident version.")
            name = type(request).__name__.lower()
            try:
                check_command("disrupt" if name == "disrupt" else name, run.status)
            except (IllegalTransition, KeyError) as exc:
                raise Conflict(str(exc)) from exc
            if isinstance(request, Clarify):
                run, event = self._clarify(run, request)
            else:
                run, event = self._revise(run, request)
            self._update(connection, run)
            self._revoke(connection, run.id)
            self._event(connection, run, event)
            return self._save_command(
                connection, scope, key, digest, Receipt(run_id=run.id, version=run.version)
            )

    @staticmethod
    def _revision(run: RunBody, **changes: object) -> RunBody:
        """Open the next revision with a clean slate for everything a worker derives."""
        return run.model_copy(
            update={
                "version": run.version + 1,
                "status": "planning",
                "clarification": None,
                "clarification_option": None,
                "evidence": run.evidence.model_copy(
                    update={"intake": None, "offers": (), "rounds": 0}
                )
                if run.evidence
                else None,
                "question": None,
                "incident": None,
                "verified_offer": None,
                "error": None,
                "skip_intake": False,
                **changes,
            }
        )

    def _revise(
        self, run: RunBody, request: Disrupt | Retract | Retry
    ) -> tuple[RunBody, EventDraft]:
        if isinstance(request, Disrupt):
            overlays = () if request.mode == "replace" else run.overlays
            return (
                self._revision(run, notice=request.notice, overlays=overlays),
                EventDraft(
                    kind="disruption_received",
                    role="operator",
                    message="A new disruption report is queued.",
                    details={"mode": request.mode},
                ),
            )
        if isinstance(request, Retry):
            if not retryable(run.status, run.error):
                raise Conflict("This failure cannot be retried.")
            return (
                self._revision(run),
                EventDraft(kind="retry_requested", role="system", message="The run is retried."),
            )
        known = {incident_id(item): item for item in run.overlays}
        missing = set(request.incident_ids) - known.keys()
        if missing:
            raise Conflict("The run has no incident with that identifier.")
        keep = tuple(item for key, item in known.items() if key not in request.incident_ids)
        event = EventDraft(
            kind="incident_retracted",
            role="operator",
            message="An incident was retracted.",
            details={"retracted": list(request.incident_ids), "remaining": len(keep)},
        )
        if not keep:
            return self._revision(run, status="ready", overlays=(), notice=None), event
        return self._revision(run, overlays=keep, incident=keep[-1], skip_intake=True), event

    @staticmethod
    def _clarify(run: RunBody, request: Clarify) -> tuple[RunBody, EventDraft]:
        if run.status != "clarification":
            raise Conflict("This run is not waiting for clarification.")
        if run.workflow == "vnext":
            question = (
                run.evidence.intake.question if run.evidence and run.evidence.intake else None
            )
            if not question or request.question_id != question.id:
                raise Conflict("This question belongs to a different revision.")
            if request.option_id and request.option_id not in {
                "unknown",
                *(item.id for item in question.options),
            }:
                raise Conflict("The option is absent from the current question.")
        elif request.answer is None or request.question_id is not None:
            raise Conflict("Legacy runs require a text answer.")
        return (
            run.model_copy(
                update={
                    "status": "planning",
                    "clarification": request.answer or request.option_id,
                    "clarification_option": request.option_id,
                    "question": None,
                }
            ),
            EventDraft(
                kind="clarification_received",
                role="operator",
                message="The operator received a clarification.",
            ),
        )

    def has_step(self, run_id: str, version: int, step: str) -> bool:
        with closing(self.connect()) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM steps WHERE run_id=? AND version=? AND step=?",
                    (run_id, version, step),
                ).fetchone()
                is not None
            )

    def step(
        self,
        run_id: str,
        version: int,
        step: str,
        *,
        event: EventDraft | None = None,
        updates: Mapping[str, object] | None = None,
        offers: tuple[Offer, ...] = (),
        votes: tuple[Vote, ...] = (),
    ) -> bool:
        with self.write() as connection:
            self._require_fence(connection, run_id)
            run = self._read(connection, run_id)
            if run.version != version or run.status != "planning":
                return False
            inserted = connection.execute(
                "INSERT INTO steps VALUES (?,?,?) ON CONFLICT DO NOTHING",
                (run_id, version, step),
            )
            if inserted.rowcount == 0:
                return False
            for ordinal, offer in enumerate(offers):
                if offer.version != version:
                    raise Conflict("Cannot persist an obsolete offer.")
                connection.execute(
                    "INSERT INTO offers VALUES (?,?,?,?,?)",
                    (run_id, version, offer.id, ordinal, offer.model_dump_json()),
                )
            for vote in votes:
                if vote.version != version:
                    raise Conflict("Cannot persist an obsolete vote.")
                connection.execute(
                    "INSERT INTO votes VALUES (?,?,?,?,?)",
                    (run_id, version, vote.offer_id, vote.rider, vote.model_dump_json()),
                )
            if updates:
                # Validate the result instead of trusting free-form updates.
                candidate = RunBody.model_validate(run.model_copy(update=updates).model_dump())
                try:
                    if candidate.status != run.status:
                        check_worker_transition(run.status, candidate.status)
                except IllegalTransition as exc:
                    raise Conflict(str(exc)) from exc
                run = candidate
                self._update(connection, run)
            if event:
                self._event(connection, run, event)
            return True

    def calls(self, run_id: str, version: int, step: str | None = None) -> list[ModelCall]:
        with closing(self.connect()) as connection:
            return [
                ModelCall.model_validate(dict(row))
                for row in connection.execute(
                    """SELECT id, step, model, digest, context, request_sha256, state, content,
                              input_tokens, output_tokens, duration_ms
                       FROM model_calls WHERE run_id=? AND version=? AND (? IS NULL OR step=?)
                       ORDER BY id""",
                    (run_id, version, step, step),
                )
            ]

    def reserve_call(
        self,
        run_id: str,
        version: int,
        step: str,
        model: str,
        digest: str,
        context: int,
        request_sha256: str = "",
    ) -> int | None:
        with self.write() as connection:
            self._require_fence(connection, run_id)
            run = self._read(connection, run_id)
            if run.version != version or run.status != "planning":
                return None
            spent = connection.execute(
                "SELECT count(*) FROM model_calls WHERE run_id=? AND version=?",
                (run_id, version),
            ).fetchone()[0]
            if spent >= 10:
                raise Conflict("Model call budget exhausted.")
            slot = connection.execute(
                """INSERT INTO model_calls (run_id,version,step,model,digest,context,request_sha256)
                   VALUES (?,?,?,?,?,?,?)""",
                (run_id, version, step, model, digest, context, request_sha256),
            ).lastrowid
            if slot is None:
                raise sqlite3.DatabaseError("The model call reservation has no row ID.")
            return slot

    def finish_call(
        self,
        run_id: str,
        version: int,
        slot: int,
        state: str,
        content: str | None,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> bool:
        with self.write() as connection:
            self._require_fence(connection, run_id)
            run = self._read(connection, run_id)
            if run.version != version or run.status != "planning":
                return False
            return (
                connection.execute(
                    """UPDATE model_calls SET state=?,content=?,input_tokens=?,output_tokens=?,
                          duration_ms=? WHERE id=? AND run_id=? AND version=?
                          AND state='pending'""",
                    (
                        state,
                        content,
                        input_tokens,
                        output_tokens,
                        duration_ms,
                        slot,
                        run_id,
                        version,
                    ),
                ).rowcount
                == 1
            )
