"""Durable run coordination over application-owned steps."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import Command, interrupt

from trl.contracts import CreateRun, EventDraft, Network, Receipt, RouteLine, RunBody
from trl.disruptions import Overlay
from trl.domain import Scenario, Vote
from trl.gtfs import Schedule
from trl.notice import rule_notice
from trl.routing import SearchIncomplete, find_offers
from trl.scenarios import load_scenario
from trl.storage import RunStore
from trl.verify import verify_offer

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    run_id: str
    version: int


class RunService:
    def __init__(self, store: RunStore, schedule: Schedule) -> None:
        self.store = store
        self.schedule = schedule
        self.tasks: dict[tuple[str, int], asyncio.Task[None]] = {}

    def new_run(self, request: CreateRun, key: str, scenario: Scenario | None = None) -> Receipt:
        scenario = scenario or load_scenario(request.scenario)
        initial = find_offers(self.schedule, scenario, limit=1)
        return self.store.create(request, key, scenario, initial[0] if initial else None)

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
        for receipt in self.store.active():
            self.enqueue(receipt)
        try:
            yield
        finally:
            tasks = tuple(self.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def execute(self, receipt: Receipt) -> None:
        current = self.store.read(receipt.run_id)
        if current.version != receipt.version or current.status != "planning":
            return
        state: GraphState = {"run_id": receipt.run_id, "version": receipt.version}
        config: RunnableConfig = {
            "configurable": {"thread_id": f"{receipt.run_id}:{receipt.version}"},
            "max_concurrency": 1,
            "recursion_limit": 24,
        }
        try:
            graph = StateGraph(GraphState)
            graph.add_node("ingest", self.ingest)  # pyright: ignore[reportUnknownMemberType]
            graph.add_node("search", self.search)  # pyright: ignore[reportUnknownMemberType]
            graph.add_node("coordinate", self.coordinate)  # pyright: ignore[reportUnknownMemberType]
            graph.add_edge(START, "ingest")
            graph.add_edge("ingest", "search")
            graph.add_edge("search", "coordinate")
            graph.add_edge("coordinate", END)
            async with AsyncSqliteSaver.from_conn_string(str(self.store.path)) as saver:
                # Initialize checkpoint DDL before competing workers open the same database.
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
        except Exception:
            logger.exception("run worker failed", extra={"run_id": receipt.run_id})
            self.store.step(
                receipt.run_id,
                receipt.version,
                "worker-error",
                updates={"status": "model_error", "error": "worker_error"},
                event=EventDraft(kind="error", role="system", message="The run could not finish."),
            )

    def ingest(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run is None or self.store.has_step(run.id, run.version, "ingest"):
            return {}
        text = run.notice or ""
        if run.clarification:
            text = f"{text}\n{run.clarification}"
        incident = rule_notice(text, self.schedule, run.scenario.service_date)
        if incident is None:
            self.store.step(
                run.id,
                run.version,
                "clarification-request",
                updates={"status": "clarification", "question": "Which stop or trip is affected?"},
                event=EventDraft(
                    kind="clarification",
                    role="operator",
                    message="The report needs clarification.",
                ),
            )
            answer: object = interrupt("Which stop or trip is affected?")
            if isinstance(answer, str):
                incident = rule_notice(answer, self.schedule, run.scenario.service_date)
        if incident is None:
            self.store.step(
                run.id,
                run.version,
                "ingest-invalid",
                updates={"status": "model_error", "error": "unresolved_notice"},
                event=EventDraft(
                    kind="error", role="operator", message="The report remains unclear."
                ),
            )
            return {}
        self.store.step(
            run.id,
            run.version,
            "ingest",
            updates={
                "incident": incident,
                "overlays": (*run.overlays, incident),
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

    def search(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run is None or run.status != "planning" or run.incident is None:
            return {}
        if self.store.has_step(run.id, run.version, "search"):
            return {}
        try:
            offers = tuple(
                find_offers(self.schedule, run.scenario, run.version, Overlay.compile(run.overlays))
            )
            updates = {} if offers else {"status": "infeasible"}
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
            updates = {"status": "search_incomplete", "error": "label_budget"}
            event = EventDraft(kind="error", role="router", message="The search budget ran out.")
        self.store.step(run.id, run.version, "search", event=event, updates=updates, offers=offers)
        return {}

    def coordinate(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run is None or run.status != "planning":
            return {}
        view = self.store.view(run.id)
        if not view.offers or view.version != run.version:
            return {}
        offer = view.offers[0]
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
