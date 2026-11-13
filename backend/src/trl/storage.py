"""Transactional application state and public event log."""

import fcntl
import hashlib
import sqlite3
from collections.abc import Generator, Mapping
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from trl.contracts import (
    Clarify,
    CreateRun,
    Disrupt,
    Event,
    EventDraft,
    Metrics,
    ModelCall,
    Receipt,
    RunBody,
    RunView,
)
from trl.domain import Offer, Record, Scenario, Vote
from trl.robustness import PROFILE, snapshot_id
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, version INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS commands (
  scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, response TEXT NOT NULL,
  PRIMARY KEY (scope, key)
);
CREATE TABLE IF NOT EXISTS steps (
  run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL, step TEXT NOT NULL,
  PRIMARY KEY (run_id, version, step)
);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL,
  recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_run_seq ON events(run_id, seq);
CREATE TABLE IF NOT EXISTS offers (
  run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL, offer_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY (run_id, version, offer_id)
);
CREATE TABLE IF NOT EXISTS votes (
  run_id TEXT NOT NULL, version INTEGER NOT NULL, offer_id TEXT NOT NULL, rider TEXT NOT NULL,
  body TEXT NOT NULL, PRIMARY KEY (run_id, version, offer_id, rider),
  FOREIGN KEY (run_id, version, offer_id) REFERENCES offers(run_id, version, offer_id)
);
CREATE TABLE IF NOT EXISTS model_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
  version INTEGER NOT NULL, step TEXT NOT NULL, model TEXT NOT NULL, digest TEXT NOT NULL,
  context INTEGER NOT NULL, request_sha256 TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT 'pending', content TEXT,
  input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS model_calls_run_version ON model_calls(run_id,version,id);
PRAGMA user_version = 2;
"""
EVENT_DRAFT = TypeAdapter(EventDraft)


class NotFound(LookupError):
    """Unknown run identifier."""


class Conflict(ValueError):
    """The command conflicts with current state or a prior request."""


class RunStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA)
        with self.write() as connection:
            if not any(
                row["name"] == "request_sha256"
                for row in connection.execute("PRAGMA table_info(model_calls)")
            ):
                connection.execute(
                    "ALTER TABLE model_calls ADD COLUMN request_sha256 TEXT NOT NULL DEFAULT ''"
                )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def execution_guard(self, run_id: str) -> Generator[bool]:
        """One process owns a run's checkpoint execution; OS releases on crash.

        Advisory locks require local storage (the supported macOS/Linux setup).
        The file is intentionally retained: unlinking creates a lock-inode race.
        """
        directory = self.path.parent / f"{self.path.name}.workers"
        directory.mkdir(exist_ok=True)
        identifier = hashlib.sha256(run_id.encode()).hexdigest()
        with (directory / identifier).open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    @contextmanager
    def write(self) -> Generator[sqlite3.Connection]:
        with closing(self.connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection

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
    ) -> Receipt:
        with self.write() as connection:
            digest, previous = self._get_command(connection, "create", key, request)
            if previous:
                return previous
            operator_mode = request.operator_mode or default_operator
            run = RunBody(
                id=uuid4().hex,
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
                    message="The initial timetable is ready.",
                ),
            )
            return self._save_command(
                connection, "create", key, digest, Receipt(run_id=run.id, version=run.version)
            )

    def command(self, run_id: str, key: str, request: Disrupt | Clarify) -> Receipt:
        scope = f"{type(request).__name__}:{run_id}"
        with self.write() as connection:
            digest, previous = self._get_command(connection, scope, key, request)
            if previous:
                return previous
            run = self._read(connection, run_id)
            if request.version != run.version:
                raise Conflict("The run has a newer incident version.")
            if isinstance(request, Disrupt):
                run = run.model_copy(
                    update={
                        "version": run.version + 1,
                        "status": "planning",
                        "notice": request.notice,
                        "clarification": None,
                        "clarification_option": None,
                        "evidence": run.evidence.model_copy(update={"intake": None, "offers": ()})
                        if run.evidence
                        else None,
                        "question": None,
                        "incident": None,
                        "verified_offer": None,
                        "error": None,
                    }
                )
                event = EventDraft(
                    kind="disruption_received",
                    role="operator",
                    message="A new disruption report is queued.",
                )
            else:
                if run.status != "clarification":
                    raise Conflict("This run is not waiting for clarification.")
                if run.workflow == "vnext":
                    question = (
                        run.evidence.intake.question
                        if run.evidence and run.evidence.intake
                        else None
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
                run = run.model_copy(
                    update={
                        "status": "planning",
                        "clarification": request.answer or request.option_id,
                        "clarification_option": request.option_id,
                        "question": None,
                    }
                )
                event = EventDraft(
                    kind="clarification_received",
                    role="operator",
                    message="The operator received a clarification.",
                )
            self._update(connection, run)
            self._event(connection, run, event)
            return self._save_command(
                connection, scope, key, digest, Receipt(run_id=run.id, version=run.version)
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
                run = run.model_copy(update=updates)
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
            assert slot is not None
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
