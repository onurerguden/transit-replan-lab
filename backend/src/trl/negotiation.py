"""Bounded negotiation steps, independent role views, and durable model replies."""

import asyncio
from time import perf_counter

from pydantic import ValidationError

from trl.agents import (
    Choice,
    Decision,
    JointDecision,
    ModelError,
    ModelPort,
    NoticeDecision,
    OllamaModel,
    RoleView,
    Stage,
    parse_decision,
    view_digest,
    view_for,
)
from trl.contracts import EventDraft, RunBody
from trl.domain import Disruption, Offer, Record, Rider, Vote
from trl.gtfs import Schedule
from trl.notice import rule_notice
from trl.observability import tracer
from trl.storage import Conflict, RunStore


class StaleRun(RuntimeError):
    """A newer incident superseded this worker."""


class Negotiator:
    def __init__(self, store: RunStore, schedule: Schedule, model: ModelPort) -> None:
        self.store = store
        self.schedule = schedule
        self.model = model

    async def ask[T: Record](
        self,
        run: RunBody,
        stage: Stage,
        key: str,
        view: RoleView,
        schema: type[T],
        *,
        attempts: int = 2,
    ) -> T:
        calls = self.store.calls(run.id, run.version, key)
        for call in calls:
            if call.state == "valid" and call.content is not None:
                return schema.model_validate_json(call.content)
        if len(calls) >= attempts and any(call.state == "pending" for call in calls):
            raise ModelError("model_interrupted")
        for attempt in range(len(calls), attempts):
            try:
                info = (
                    await self.model.stage_info(stage)
                    if isinstance(self.model, OllamaModel)
                    else await self.model.info()
                )
            except Exception as exc:
                raise ModelError("model_unavailable") from exc
            try:
                slot = await asyncio.to_thread(
                    self.store.reserve_call,
                    run.id,
                    run.version,
                    key,
                    info.name,
                    info.digest,
                    info.context,
                    view_digest(stage, view),
                )
            except Conflict as exc:
                raise ModelError("call_budget") from exc
            if slot is None:
                raise StaleRun()
            start = perf_counter()
            state = "valid"
            content = None
            input_tokens = output_tokens = 0
            decision = None
            attrs = {
                "gen_ai.operation.name": "chat",
                "gen_ai.provider.name": "replay" if info.name == "replay" else "ollama",
                "gen_ai.request.model": info.name,
                "trl.model.digest": info.digest,
                "trl.model.step": key,
                "trl.model.context": info.context,
            }
            with tracer().start_as_current_span("model.call", attributes=attrs) as span:
                try:
                    reply = await self.model.generate(stage, view, schema, repair=attempt > 0)
                    input_tokens, output_tokens = reply.input_tokens, reply.output_tokens
                    decision = schema.model_validate_json(reply.content)
                    content = decision.model_dump_json()
                except ValidationError:
                    state = "invalid"
                except Exception:
                    state = "error"
                span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                span.set_attribute("trl.model.result", state)
            saved = await asyncio.to_thread(
                self.store.finish_call,
                run.id,
                run.version,
                slot,
                state,
                content,
                input_tokens,
                output_tokens,
                round((perf_counter() - start) * 1000),
            )
            if not saved:
                raise StaleRun()
            if decision is not None:
                return decision
            if state == "error":
                raise ModelError("inference_error")
        raise ModelError("schema_error")

    async def notice(self, run: RunBody) -> Disruption | None:
        step = "operator:clarified" if run.clarification else "operator:ingest"
        view = view_for("operator", run, self.schedule)
        result = await self.ask(run, "operator", step, view, NoticeDecision)
        event = parse_decision(result, self.schedule, run.scenario.service_date)
        evidence = rule_notice(str(view["notice"]), self.schedule, run.scenario.service_date)
        return event if event == evidence else None

    def stored_choice(self, run: RunBody, key: str) -> Choice | None:
        for call in self.store.calls(run.id, run.version, key):
            if call.state == "valid" and call.content is not None:
                return Choice.model_validate_json(call.content)
        return None

    async def pick(
        self,
        run: RunBody,
        stage: Stage,
        key: str,
        offers: tuple[Offer, ...],
        *,
        rider: Rider | None = None,
        choices: tuple[str, ...] = (),
    ) -> Choice:
        view = view_for(stage, run, self.schedule, offers, rider=rider, choices=choices)
        decision = await self.ask(run, stage, key, view, Choice)
        if decision.offer not in {item.id for item in offers}:
            raise ModelError("unknown_offer")
        await asyncio.to_thread(
            self.store.step,
            run.id,
            run.version,
            key,
            event=EventDraft(
                kind=stage,
                role=f"rider_{rider}" if rider else stage,
                message={
                    "first": "Selected an independent first preference.",
                    "analyst": "Prioritized a transfer candidate.",
                    "mediator": "Selected a compromise offer.",
                }[stage],
                details={"offer_id": decision.offer, "reason": decision.reason},
            ),
        )
        return decision

    async def ballot(
        self,
        run: RunBody,
        rider: Rider,
        number: int,
        offered: str,
        pool: tuple[Offer, ...],
    ) -> str | None:
        view = view_for("vote", run, self.schedule, pool, rider=rider, proposed=offered)
        key = f"vote:{number}:{rider}"
        decision = await self.ask(run, "vote", key, view, Decision)
        ids = {item.id for item in pool}
        if (
            decision.offer not in ids
            or (decision.action in {"accept", "reject"} and decision.offer != offered)
            or (decision.action == "counter" and decision.offer == offered)
        ):
            raise ModelError("invalid_vote")
        await self.vote(
            run,
            key,
            rider,
            offered,
            decision.action == "accept",
            decision.action,
            decision.reason,
        )
        if decision.action == "accept":
            return offered
        return decision.offer if decision.action == "counter" else None

    async def vote(
        self,
        run: RunBody,
        key: str,
        rider: Rider,
        offer: str,
        accepted: bool,
        action: str,
        reason: str,
    ) -> None:
        vote = Vote(rider=rider, offer_id=offer, version=run.version, accepted=accepted)
        await asyncio.to_thread(
            self.store.step,
            run.id,
            run.version,
            key,
            votes=(vote,),
            event=EventDraft(
                kind="vote",
                role=f"rider_{rider}",
                message={
                    "accept": "Accepted the offer.",
                    "reject": "Rejected the offer.",
                    "counter": "Requested a different offer.",
                }[action],
                details={"offer_id": offer, "accepted": accepted, "reason": reason},
            ),
        )

    async def single(self, run: RunBody, offers: tuple[Offer, ...]) -> str | None:
        decision = await self.ask(
            run,
            "single",
            "single:1",
            view_for("single", run, self.schedule, offers),
            JointDecision,
        )
        if decision.offer not in {offer.id for offer in offers}:
            raise ModelError("unknown_offer")
        ballots: tuple[tuple[Rider, bool], ...] = (
            ("a", decision.accept_a),
            ("b", decision.accept_b),
        )
        for rider, accepted in ballots:
            await self.vote(
                run,
                f"vote:1:{rider}",
                rider,
                decision.offer,
                accepted,
                "accept" if accepted else "reject",
                "single_coordinator",
            )
        return decision.offer if decision.accept_a and decision.accept_b else None

    async def negotiate(self, run: RunBody, offers: tuple[Offer, ...]) -> str | None:
        choices = tuple(
            result.offer
            for rider in ("a", "b")
            if (result := self.stored_choice(run, f"first:{rider}")) is not None
        )
        if len(choices) != 2:
            raise ModelError("missing_first_preference")
        analyst = self.stored_choice(run, "analyst:1")
        preferred = analyst.offer if analyst else ""

        def priority(item: Offer) -> bool:
            return item.id != preferred

        pool: tuple[Offer, ...] = tuple(sorted(offers, key=priority))
        for round_number in range(1, (2 if run.counteroffers else 1) + 1):
            if not pool:
                break
            valid_choices = [
                choice for choice in choices if any(item.id == choice for item in pool)
            ]
            if len(valid_choices) == 2 and valid_choices[0] == valid_choices[1]:
                proposed = valid_choices[0]
            elif run.architecture == "five":
                decision = await self.pick(
                    run,
                    "mediator",
                    f"mediator:{round_number}",
                    pool,
                    choices=choices,
                )
                proposed = decision.offer
            else:
                proposed = next(iter(valid_choices), pool[0].id)
            await asyncio.to_thread(
                self.store.step,
                run.id,
                run.version,
                f"propose:{round_number}",
                event=EventDraft(
                    kind="proposal",
                    role="system",
                    message=f"Offer sent for round {round_number}.",
                    details={"offer_id": proposed, "round": round_number},
                ),
            )
            a = await self.ballot(run, "a", round_number, proposed, pool)
            b = await self.ballot(run, "b", round_number, proposed, pool)
            if a == b == proposed:
                return proposed
            choices = tuple(value for value in (a, b) if value is not None and value != proposed)
            pool = tuple(item for item in pool if item.id != proposed)
        return None
