"""Durable run coordination over application-owned steps."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TypedDict

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import Command, Send, interrupt

from trl.agents import ModelError, ModelPort, configured_model
from trl.contracts import CreateRun, EventDraft, Network, Receipt, RouteLine, RunBody
from trl.disruptions import Overlay
from trl.domain import Architecture, Rider, Scenario, Vote
from trl.gtfs import Schedule
from trl.negotiation import Negotiator, StaleRun
from trl.notice import rule_notice
from trl.observability import observe, observe_async, tracer
from trl.routing import SearchIncomplete, find_offers
from trl.scenarios import load_scenario
from trl.storage import RunStore
from trl.verify import verify_offer

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
        attributes = {"trl.run_id": receipt.run_id, "trl.version": receipt.version}
        with tracer().start_as_current_span("simulation.run", attributes=attributes) as span:
            trace_id = f"{span.get_span_context().trace_id:032x}"
            with structlog.contextvars.bound_contextvars(run_id=receipt.run_id, trace_id=trace_id):
                await self._execute(receipt)
                state = self.store.read(receipt.run_id)
                if state.version == receipt.version:
                    span.set_attribute("trl.outcome", state.status)
                    logger.info("run_state", status=state.status, version=state.version)

    async def _execute(self, receipt: Receipt) -> None:
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
            graph = self.build_graph(current.architecture)
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
        except StaleRun:
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
                updates={"status": "model_error", "error": "worker_error"},
                event=EventDraft(kind="error", role="system", message="The run could not finish."),
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
        run = self.active_run(state)
        if run is None or self.store.has_step(run.id, run.version, "ingest"):
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

    @observe("search")
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

    @observe("coordinate")
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

    @observe_async("analyst")
    async def analyst(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
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
        offers = self.store.view(run.id).offers
        if affected and offers:
            await self.negotiator.pick(run, "analyst", "analyst:1", offers)
        return {}

    @observe_async("first")
    async def first(self, state: RiderState) -> dict[str, object]:
        run = self.active_run(state)
        if run and run.status == "planning":
            rider = state["rider"]
            offers = self.store.view(run.id).offers
            if offers:
                await self.negotiator.pick(run, "first", f"first:{rider}", offers, rider=rider)
        return {}

    @observe_async("negotiate")
    async def negotiate(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run and run.status == "planning":
            offer_id = await self.negotiator.negotiate(run, self.store.view(run.id).offers)
            await asyncio.to_thread(self.complete_negotiation, run, offer_id)
        return {}

    @observe_async("single")
    async def single(self, state: GraphState) -> dict[str, object]:
        run = self.active_run(state)
        if run and run.status == "planning":
            offer_id = await self.negotiator.single(run, self.store.view(run.id).offers)
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
