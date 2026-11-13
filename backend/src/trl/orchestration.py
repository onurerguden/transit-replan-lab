"""Durable run coordination over application-owned steps."""

import asyncio
import json
import os
import sqlite3
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, closing, suppress
from typing import Literal, TypedDict

import httpx
import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import Command, Send, interrupt

from trl import metrics
from trl.agents import ModelError, ModelPort, OllamaModel, configured_model
from trl.contracts import CreateRun, EventDraft, Network, Receipt, RouteLine, RunBody
from trl.disruptions import Overlay
from trl.domain import Architecture, Disruption, Offer, Rider, Scenario, Vote
from trl.gtfs import DATA_ROOT, Schedule
from trl.intake import (
    MAX_ROUNDS,
    answer_facts,
    conjoined_variants,
    decide,
    extract,
    lexicon_proposal,
    refused,
    slot_facts,
)
from trl.lifecycle import SETTLED
from trl.negotiation import Negotiator, StaleRun
from trl.notice import rule_notice
from trl.observability import observe, observe_async, tracer
from trl.robustness import compare
from trl.routing import SearchIncomplete, SearchStats, find_offers
from trl.scenarios import load_scenario
from trl.storage import Fence, Fenced, NotFound, RunStore, current_fence
from trl.verify import verify_offer
from trl.vnext import Extraction, Intake, OperatorMode, preferred_offer


def with_incident(
    incidents: tuple[Disruption, ...], incident: Disruption
) -> tuple[Disruption, ...]:
    """Add an incident once, so a retried revision does not stack a duplicate."""
    return incidents if incident in incidents else (*incidents, incident)


logger = structlog.get_logger(__name__)


class GraphState(TypedDict):
    run_id: str
    version: int


class RiderState(GraphState):
    rider: Rider


def first_riders(state: GraphState) -> list[Send]:
    return [
        Send("first", RiderState(run_id=state["run_id"], version=state["version"], rider=rider))
        for rider in ("a", "b")
    ]


class RunService:
    def __init__(
        self,
        store: RunStore,
        schedule: Schedule,
        model: ModelPort | None = None,
    ) -> None:
        self.store = store
        self.schedule = schedule
        self.negotiator = Negotiator(store, schedule, model or configured_model(schedule))
        self.default_operator: OperatorMode = "rules"
        self.tasks: dict[tuple[str, int], asyncio.Task[None]] = {}
        self.changed = asyncio.Event()

    async def configure_default_operator(self) -> None:
        model = self.negotiator.model
        decision_path = DATA_ROOT / "fixtures" / "vnext-decision.json"
        if not isinstance(model, OllamaModel) or not decision_path.is_file():
            return
        try:
            decision = json.loads(decision_path.read_text())
            if decision.get("default_operator") != "hybrid" or model.operator_model:
                return
            installed = await asyncio.wait_for(model.info(), timeout=2)
            if installed.digest == decision.get("model_digest"):
                self.default_operator = "hybrid"
        except (OSError, ValueError, AttributeError, TimeoutError, ModelError, httpx.HTTPError):
            logger.info("operator_default_rules")

    def new_run(self, request: CreateRun, key: str, scenario: Scenario | None = None) -> Receipt:
        scenario = scenario or load_scenario(request.scenario)
        try:
            initial, complete = find_offers(self.schedule, scenario, limit=1), True
        except SearchIncomplete:
            # Record the exhausted search instead of failing the create command.
            initial, complete = [], False
        return self.store.create(
            request,
            key,
            scenario,
            initial[0] if initial else None,
            default_operator=self.default_operator if request.workflow == "vnext" else "rules",
            initial_complete=complete,
        )

    def network(self) -> Network:
        lines: dict[str, RouteLine] = {}
        for trip in self.schedule.trips.values():
            if trip.route not in lines or len(trip.calls) > len(lines[trip.route].stops):
                lines[trip.route] = RouteLine(
                    id=trip.route,
                    mode="metro" if trip.route.startswith("metro:") else "tram",
                    stops=tuple(call.stop for call in trip.calls),
                )
        return Network(stops=tuple(self.schedule.stops.values()), lines=tuple(lines.values()))

    def active_run(self, state: GraphState) -> RunBody | None:
        run = self.store.read(state["run_id"])
        return run if run.version == state["version"] else None

    def enqueue(self, receipt: Receipt) -> None:
        key = (receipt.run_id, receipt.version)
        existing = self.tasks.get(key)
        if existing and not existing.done():
            return
        for (run_id, version), task in tuple(self.tasks.items()):
            if run_id == receipt.run_id and version < receipt.version and not task.done():
                # A newer revision supersedes the running one. Its lease is already revoked.
                task.cancel()
        self.tasks[key] = asyncio.create_task(self.execute(receipt))
        self.tasks[key].add_done_callback(lambda task: self.finished(key, task))

    def finished(self, key: tuple[str, int], task: asyncio.Task[None]) -> None:
        if self.tasks.get(key) is task:
            self.tasks.pop(key, None)
            run = self.store.read(key[0])
            if not task.cancelled() and run.version == key[1] and run.status == "planning":
                if run.clarification and not self.store.has_step(run.id, run.version, "ingest"):
                    self.enqueue(Receipt(run_id=run.id, version=run.version))

    @asynccontextmanager
    async def workers(self) -> AsyncGenerator[None]:
        loop = asyncio.get_running_loop()
        self.changed = asyncio.Event()

        def notify() -> None:
            loop.call_soon_threadsafe(self.changed.set)

        self.store.subscribers.append(notify)
        await asyncio.to_thread(self.prune_checkpoints)
        for receipt in await asyncio.to_thread(self.store.active):
            self.enqueue(receipt)
        try:
            yield
        finally:
            self.store.subscribers.remove(notify)
            tasks = tuple(self.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def wait_for_change(self, seconds: float) -> None:
        """Sleep until a commit in this process, or until the timeout for other processes."""
        self.changed.clear()
        with suppress(TimeoutError):
            async with asyncio.timeout(seconds):
                await self.changed.wait()

    async def execute(self, receipt: Receipt) -> None:
        attributes = {"trl.run_id": receipt.run_id, "trl.version": receipt.version}
        with tracer().start_as_current_span("simulation.run", attributes=attributes) as span:
            trace_id = f"{span.get_span_context().trace_id:032x}"
            with structlog.contextvars.bound_contextvars(run_id=receipt.run_id, trace_id=trace_id):
                await self._execute(receipt)
                state = await asyncio.to_thread(self.store.read, receipt.run_id)
                if state.version == receipt.version:
                    if state.status in SETTLED:
                        metrics.RUNS_SETTLED.labels(state.status).inc()
                    span.set_attribute("trl.outcome", state.status)
                    logger.info("run_state", status=state.status, version=state.version)

    async def _execute(self, receipt: Receipt) -> None:
        owner = f"{os.getpid()}:{id(self)}"
        delay = 0.05
        while True:
            current = await asyncio.to_thread(self.store.read, receipt.run_id)
            if current.version != receipt.version or current.status != "planning":
                return
            fence = await asyncio.to_thread(
                self.store.acquire_lease, receipt.run_id, receipt.version, owner
            )
            if fence is not None:
                await self._with_lease(receipt, fence)
                return
            # Another live worker owns this revision. Retry with a bounded backoff.
            await self.wait_for_change(delay)
            delay = min(delay * 2, 1.0)

    async def _with_lease(self, receipt: Receipt, fence: Fence) -> None:
        worker = asyncio.current_task()
        lost = False

        async def beat() -> None:
            nonlocal lost
            while True:
                await asyncio.sleep(self.store.lease_ttl / 4)
                if not await asyncio.to_thread(self.store.heartbeat, fence):
                    lost = True
                    if worker is not None:
                        worker.cancel()
                    return

        heartbeat = asyncio.create_task(beat())
        token = current_fence.set(fence)
        try:
            await self._execute_owned(receipt)
        except Fenced:
            logger.info("lease_revoked", run_id=receipt.run_id)
        except asyncio.CancelledError:
            # Losing the lease is not a shutdown. Only an outside cancel propagates.
            if not lost:
                raise
            asyncio.current_task().uncancel()  # pyright: ignore[reportOptionalMemberAccess]
            logger.info("lease_lost", run_id=receipt.run_id)
        finally:
            heartbeat.cancel()
            current_fence.reset(token)
            await asyncio.shield(asyncio.to_thread(self.store.release_lease, fence))

    def prune_checkpoints(self) -> int:
        """Delete execution checkpoints for revisions that can no longer resume."""
        path = self.store.checkpoint_path
        if not path.exists():
            return 0
        with closing(sqlite3.connect(path)) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
            if not {"checkpoints", "writes"} <= tables:
                return 0
            threads = [
                row[0] for row in connection.execute("SELECT DISTINCT thread_id FROM checkpoints")
            ]
            stale = [thread for thread in threads if self._stale_thread(thread)]
            for thread in stale:
                connection.execute("DELETE FROM writes WHERE thread_id=?", (thread,))
                connection.execute("DELETE FROM checkpoints WHERE thread_id=?", (thread,))
            connection.commit()
            return len(stale)

    def _stale_thread(self, thread: str) -> bool:
        run_id, _, version = thread.rpartition(":")
        try:
            run = self.store.read(run_id)
        except NotFound:
            return True
        return run.version != int(version) or run.status not in {"planning", "clarification"}

    async def _execute_owned(self, receipt: Receipt) -> None:
        current = await asyncio.to_thread(self.store.read, receipt.run_id)
        if current.version != receipt.version or current.status != "planning":
            return
        state: GraphState = {"run_id": receipt.run_id, "version": receipt.version}
        config: RunnableConfig = {
            "configurable": {"thread_id": f"{receipt.run_id}:{receipt.version}"},
            "max_concurrency": 1,
            "recursion_limit": 24,
        }
        try:
            graph = self.build_graph(current.architecture)
            async with AsyncSqliteSaver.from_conn_string(str(self.store.checkpoint_path)) as saver:
                async with saver.conn.execute("PRAGMA busy_timeout=5000"):
                    pass
                compiled = graph.compile(checkpointer=saver)  # pyright: ignore[reportUnknownMemberType]
                checkpoint = await compiled.aget_state(config)
                entry: Command[str] | GraphState | None
                if checkpoint.interrupts and current.clarification:
                    entry = Command(resume=current.clarification)
                elif checkpoint.next:
                    entry = None
                else:
                    entry = state
                await compiled.ainvoke(entry, config, durability="sync")  # pyright: ignore[reportUnknownMemberType]
                final = await asyncio.to_thread(self.store.read, receipt.run_id)
                if final.status in SETTLED:
                    # A settled revision never resumes, so its execution checkpoints can go.
                    await saver.adelete_thread(config["configurable"]["thread_id"])
        except (StaleRun, Fenced):
            return
        except ModelError as exc:
            await asyncio.to_thread(
                self.store.step,
                receipt.run_id,
                receipt.version,
                "model-error",
                updates={"status": "model_error", "error": str(exc)},
                event=EventDraft(
                    kind="error",
                    role="system",
                    message="The local model could not decide.",
                    details={"reason": str(exc)},
                ),
            )
        except Exception:
            logger.exception("run worker failed", extra={"run_id": receipt.run_id})
            await asyncio.to_thread(
                self.store.step,
                receipt.run_id,
                receipt.version,
                "worker-error",
                updates={"status": "system_error", "error": "internal_error"},
                event=EventDraft(
                    kind="error",
                    role="system",
                    message="The run could not finish because of an internal error.",
                ),
            )

    def build_graph(
        self,
        architecture: Architecture,
    ) -> StateGraph[GraphState, None, GraphState, GraphState]:
        graph = StateGraph(GraphState)
        graph.add_node("ingest", self.ingest)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("search", self.search)  # pyright: ignore[reportUnknownMemberType]
        graph.add_edge(START, "ingest")
        graph.add_edge("ingest", "search")
        if architecture in {"rules", "single"}:
            coordinator = self.coordinate if architecture == "rules" else self.single
            graph.add_node("coordinate", coordinator)  # pyright: ignore[reportUnknownMemberType]
            graph.add_edge("search", "coordinate")
            graph.add_edge("coordinate", END)
        else:
            graph.add_node("analyst", self.analyst)  # pyright: ignore[reportUnknownMemberType]
            graph.add_node("first", self.first, input_schema=RiderState)  # pyright: ignore[reportUnknownMemberType]
            graph.add_node("negotiate", self.negotiate)  # pyright: ignore[reportUnknownMemberType]
            graph.add_edge("search", "analyst")
            graph.add_conditional_edges("analyst", first_riders, ["first"])
            graph.add_edge("first", "negotiate")
            graph.add_edge("negotiate", END)
        return graph

    @observe_async("ingest")
    async def ingest(self, state: GraphState) -> dict[str, object]:
        run = await asyncio.to_thread(self.active_run, state)
        if run is None or await asyncio.to_thread(
            self.store.has_step, run.id, run.version, "ingest"
        ):
            return {}
        if run.skip_intake:
            await asyncio.to_thread(
                self.store.step,
                run.id,
                run.version,
                "ingest",
                event=EventDraft(
                    kind="incident",
                    role="operator",
                    message="The remaining incidents stand. Replanning.",
                    details={"incidents": len(run.overlays)},
                ),
            )
            return {}
        if run.workflow == "vnext":
            await self.ingest_vnext(run)
            return {}
        text = run.notice or ""
        if run.clarification:
            text = f"{text}\n{run.clarification}"
        incident = (
            rule_notice(text, self.schedule, run.scenario.service_date)
            if run.architecture == "rules"
            else await self.negotiator.notice(run)
        )
        if incident is None and not run.clarification:
            question = "Which stop or trip is affected, and when?"
            await asyncio.to_thread(
                self.store.step,
                run.id,
                run.version,
                "clarification-request",
                updates={"status": "clarification", "question": question},
                event=EventDraft(
                    kind="clarification", role="operator", message="The report needs clarification."
                ),
            )
            answer: object = interrupt(question)
            if isinstance(answer, str):
                # The HTTP command is the authority for the current answer.
                latest = self.active_run(state)
                if latest and latest.clarification:
                    return await self.ingest(state)
        if incident is None:
            await asyncio.to_thread(
                self.store.step,
                run.id,
                run.version,
                "ingest-invalid",
                updates={"status": "model_error", "error": "unresolved_notice"},
                event=EventDraft(
                    kind="error", role="operator", message="The report remains unclear."
                ),
            )
            return {}
        await asyncio.to_thread(
            self.store.step,
            run.id,
            run.version,
            "ingest",
            updates={
                "incident": incident,
                "overlays": with_incident(run.overlays, incident),
                "status": "planning",
            },
            event=EventDraft(
                kind="incident",
                role="operator",
                message="Disruption recorded.",
                details={"kind": incident.kind},
            ),
        )
        return {}

    def preview_incident(
        self, run: RunBody, incident: Disruption
    ) -> tuple[Literal["feasible", "infeasible", "search_incomplete"], Offer | None]:
        try:
            offers = find_offers(
                self.schedule,
                run.scenario,
                run.version,
                Overlay.compile((*run.overlays, incident)),
                limit=1,
            )
        except SearchIncomplete:
            metrics.SEARCH_INCOMPLETE.inc()
            return "search_incomplete", None
        return ("feasible", offers[0]) if offers else ("infeasible", None)

    async def ingest_vnext(self, run: RunBody) -> None:
        if run.evidence is None:
            raise ValueError("A vNext run requires evidence.")
        date = run.scenario.service_date
        reasons: tuple[str, ...] = ()
        rounds = run.evidence.rounds
        declined = False
        proposal: Extraction | None = None
        if run.clarification is not None and run.evidence.intake:
            rounds += 1
            facts = answer_facts(
                run.evidence.intake,
                run.clarification,
                run.clarification_option,
                self.schedule,
                date,
            )
            if not facts:
                if run.clarification_option is None and not refused(run.clarification, date):
                    # An answer that cannot be read asks the same question again.
                    facts = run.evidence.intake.facts
                else:
                    declined = True
        else:
            notice = run.notice or ""
            proposal = lexicon_proposal(notice) if run.operator_mode == "lexicon" else None
            facts, reasons = extract(notice, self.schedule, date, proposal)
            if run.operator_mode == "hybrid" and not slot_facts(facts, "kind") and not reasons:
                proposal = await self.negotiator.ask(
                    run,
                    "operator_vnext",
                    "operator:source",
                    {"notice": notice},
                    Extraction,
                    attempts=1,
                )
                facts, reasons = extract(notice, self.schedule, date, proposal)

        def evaluate(
            incident: Disruption,
        ) -> tuple[Literal["feasible", "infeasible", "search_incomplete"], Offer | None]:
            return self.preview_incident(run, incident)

        if reasons == ("conflicting_targets",):
            group = await asyncio.to_thread(self.conjoined, run, evaluate, proposal)
            if group is not None:
                await self.record_group(run, *group)
                return

        decision = await asyncio.to_thread(
            decide,
            facts,
            reasons,
            self.schedule,
            date,
            evaluate,
            run.version,
            answered=declined or (run.clarification is not None and rounds >= MAX_ROUNDS),
        )
        evidence = run.evidence.model_copy(update={"intake": decision, "rounds": rounds})
        if decision.question:
            prompt = decision.question.prompt
            persisted = await asyncio.to_thread(
                self.store.step,
                run.id,
                run.version,
                f"clarification-request-{rounds}",
                updates={"status": "clarification", "question": prompt, "evidence": evidence},
                event=EventDraft(kind="clarification", role="operator", message=prompt),
            )
            if not persisted and not await asyncio.to_thread(
                self.store.has_step, run.id, run.version, f"clarification-request-{rounds}"
            ):
                raise StaleRun()
            answer: object = interrupt(prompt)
            if isinstance(answer, str):
                latest = await asyncio.to_thread(self.store.read, run.id)
                if latest.version == run.version and latest.clarification:
                    await self.ingest_vnext(latest)
            return
        if decision.selected is None:
            await asyncio.to_thread(
                self.store.step,
                run.id,
                run.version,
                "ingest-abstain",
                updates={"status": "abstained", "evidence": evidence},
                event=EventDraft(
                    kind="abstained",
                    role="operator",
                    message="The report did not support a single disruption.",
                ),
            )
            return
        incident = decision.selected.incident
        await asyncio.to_thread(
            self.store.step,
            run.id,
            run.version,
            "ingest",
            updates={
                "incident": incident,
                "overlays": with_incident(run.overlays, incident),
                "evidence": evidence,
                "status": "planning",
            },
            event=EventDraft(
                kind="incident",
                role="operator",
                message="Disruption recorded from verified report fields.",
                details={"kind": incident.kind},
            ),
        )

    def conjoined(
        self,
        run: RunBody,
        evaluate: Callable[
            [Disruption],
            tuple[Literal["feasible", "infeasible", "search_incomplete"], Offer | None],
        ],
        proposal: Extraction | None = None,
    ) -> tuple[Intake, tuple[Disruption, ...]] | None:
        """Read `A and B closed` as separate incidents when each part reads on its own."""
        date = run.scenario.service_date
        decisions: list[Intake] = []
        for variant in conjoined_variants(run.notice or "", self.schedule, date):
            facts, reasons = extract(variant, self.schedule, date, proposal)
            decision = decide(facts, reasons, self.schedule, date, evaluate, run.version)
            if decision.action != "apply" or decision.selected is None:
                return None
            decisions.append(decision)
        if len(decisions) < 2:
            return None
        return decisions[0], tuple(item.selected.incident for item in decisions if item.selected)

    async def record_group(
        self, run: RunBody, decision: Intake, incidents: tuple[Disruption, ...]
    ) -> None:
        overlays = run.overlays
        for incident in incidents:
            overlays = with_incident(overlays, incident)
        assert run.evidence is not None  # noqa: S101
        await asyncio.to_thread(
            self.store.step,
            run.id,
            run.version,
            "ingest",
            updates={
                "incident": incidents[-1],
                "overlays": overlays,
                "evidence": run.evidence.model_copy(update={"intake": decision}),
                "status": "planning",
            },
            event=EventDraft(
                kind="incident",
                role="operator",
                message="Several disruptions recorded from verified report fields.",
                details={"kind": incidents[-1].kind, "count": len(incidents)},
            ),
        )

    @observe("search")
    def search(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run is None or run.status != "planning" or run.incident is None:
            return {}
        if self.store.has_step(run.id, run.version, "search"):
            return {}
        try:
            overlay = Overlay.compile(run.overlays)
            work = SearchStats()
            offers = tuple(
                find_offers(
                    self.schedule,
                    run.scenario,
                    run.version,
                    overlay,
                    diverse=run.workflow == "vnext",
                    initial=run.initial,
                    stats=work,
                )
            )
            metrics.SEARCH_WORK.observe(work.work)
            updates: dict[str, object] = {}
            if run.evidence and offers:
                offers, evidence = compare(
                    self.schedule,
                    run.scenario,
                    offers,
                    overlay,
                    run.initial,
                    run.route_policy,
                )
                updates["evidence"] = run.evidence.model_copy(update={"offers": evidence})
            if not offers:
                updates["status"] = "infeasible"
            event = EventDraft(
                kind="offers" if offers else "infeasible",
                role="router",
                message=f"{len(offers)} joint offers found."
                if offers
                else "No joint arrival within the search window.",
                details={"count": len(offers)},
            )
        except SearchIncomplete:
            offers = ()
            updates = {"status": "search_incomplete", "error": "search_budget"}
            event = EventDraft(kind="error", role="router", message="The search budget ran out.")
        self.store.step(run.id, run.version, "search", event=event, updates=updates, offers=offers)
        return {}

    @observe("coordinate")
    def coordinate(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run is None or run.status != "planning":
            return {}
        view = self.store.view(run.id)
        if not view.offers or view.version != run.version:
            return {}
        offer = preferred_offer(view.offers, run.preference_a, run.preference_b)
        for rider in ("a", "b"):
            vote = Vote(rider=rider, version=run.version, offer_id=offer.id, accepted=True)
            self.store.step(
                run.id,
                run.version,
                f"vote:1:{rider}",
                votes=(vote,),
                event=EventDraft(
                    kind="vote",
                    role=f"rider_{rider}",
                    message="Accepted the offer.",
                    details={"offer_id": offer.id, "accepted": True},
                ),
            )
        self.finalize(run, offer.id)
        return {}

    @observe_async("analyst")
    async def analyst(self, state: GraphState) -> dict[str, object]:
        run = await asyncio.to_thread(self.active_run, state)
        if not run or run.status != "planning" or run.architecture != "five" or not run.initial:
            return {}
        incident = run.incident
        if incident is None:
            return {}
        routes = (run.initial.a, run.initial.b)
        affected = any(
            any(leg.kind == "walk" for leg in route.legs)
            and any(
                (
                    incident.stop in {leg.origin, leg.destination}
                    if incident.kind == "stop_closure"
                    else leg.kind == "ride" and leg.trip == incident.trip
                )
                for leg in route.legs
            )
            for route in routes
        )
        offers = (await asyncio.to_thread(self.store.view, run.id)).offers
        if affected and offers:
            await self.negotiator.pick(run, "analyst", "analyst:1", offers)
        return {}

    @observe_async("first")
    async def first(self, state: RiderState) -> dict[str, object]:
        run = await asyncio.to_thread(self.active_run, state)
        if run and run.status == "planning":
            rider = state["rider"]
            offers = (await asyncio.to_thread(self.store.view, run.id)).offers
            if offers:
                await self.negotiator.pick(run, "first", f"first:{rider}", offers, rider=rider)
        return {}

    @observe_async("negotiate")
    async def negotiate(self, state: GraphState) -> dict[str, object]:
        run = await asyncio.to_thread(self.active_run, state)
        if run and run.status == "planning":
            offer_id = await self.negotiator.negotiate(
                run, (await asyncio.to_thread(self.store.view, run.id)).offers
            )
            await asyncio.to_thread(self.complete_negotiation, run, offer_id)
        return {}

    @observe_async("single")
    async def single(self, state: GraphState) -> dict[str, object]:
        run = await asyncio.to_thread(self.active_run, state)
        if run and run.status == "planning":
            offer_id = await self.negotiator.single(
                run, (await asyncio.to_thread(self.store.view, run.id)).offers
            )
            await asyncio.to_thread(self.complete_negotiation, run, offer_id)
        return {}

    def complete_negotiation(self, run: RunBody, offer_id: str | None) -> None:
        if offer_id is not None:
            self.finalize(run, offer_id)
        else:
            self.store.step(
                run.id,
                run.version,
                "finalize",
                updates={"status": "no_agreement"},
                event=EventDraft(
                    kind="no_agreement",
                    role="system",
                    message="The riders did not reach agreement.",
                ),
            )

    @observe("finalize")
    def finalize(self, run: RunBody, offer_id: str) -> None:
        view = self.store.view(run.id)
        if view.version != run.version:
            return
        offer = next(item for item in view.offers if item.id == offer_id)
        votes = tuple(vote for vote in view.votes if vote.offer_id == offer_id)
        error = verify_offer(
            self.schedule,
            run.scenario,
            offer,
            votes,
            run.version,
            Overlay.compile(run.overlays),
        )
        self.store.step(
            run.id,
            run.version,
            "finalize",
            updates={
                "status": "verification_failed" if error else "verified",
                "error": error,
                "verified_offer": None if error else offer.id,
            },
            event=EventDraft(
                kind="verification_failed" if error else "verified",
                role="verifier",
                message="The verifier rejected the plan."
                if error
                else "Both votes and the timetable agree.",
                details={"offer_id": offer.id},
            ),
        )
