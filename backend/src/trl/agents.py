"""Local model port, role-specific data projections, and typed decisions."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

import httpx
from langchain_ollama import ChatOllama
from pydantic import JsonValue

from trl.contracts import RunBody
from trl.domain import (
    Disruption,
    Offer,
    Record,
    Rider,
    StopClosure,
    TripCancellation,
    TripDelay,
)
from trl.gtfs import DATA_ROOT, Schedule, service_second
from trl.notice import rule_notice
from trl.settings import DEFAULT_MODEL, get_settings
from trl.vnext import Extraction, preference_cost

PROMPT_VERSION = "1"
PROMPT_DIR = Path(__file__).with_name("prompts")
RoleView = dict[str, JsonValue]
Stage = Literal["operator_vnext", "operator", "analyst", "first", "mediator", "vote", "single"]
MODEL = DEFAULT_MODEL


def view_digest(stage: Stage, view: RoleView) -> str:
    revision = "2" if stage == "operator_vnext" or "vnext_preferences" in view else PROMPT_VERSION
    return hashlib.sha256(
        json.dumps(
            [revision, stage, view],
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()


class NoticeDecision(Record):
    kind: Literal["stop_closure", "trip_cancellation", "trip_delay", "clarify"]
    stop: str | None = None
    start: str | None = None
    end: str | None = None
    trip: str | None = None
    minutes: int | None = None


class Choice(Record):
    offer: str
    reason: Literal["earliest", "less_wait", "fewer_transfers", "valid", "alternative"]


class Decision(Record):
    offer: str
    action: Literal["accept", "reject", "counter"]
    reason: Literal["valid", "less_wait", "fewer_transfers", "alternative", "unacceptable"]


class JointDecision(Record):
    offer: str
    accept_a: bool
    accept_b: bool


@dataclass(frozen=True)
class ModelInfo:
    name: str
    digest: str
    context: int


@dataclass(frozen=True)
class ModelReply:
    content: str
    input_tokens: int
    output_tokens: int


class ModelError(RuntimeError):
    """A local model failed or produced an unusable decision."""


class ModelPort(Protocol):
    async def info(self) -> ModelInfo: ...
    async def generate(
        self,
        stage: Stage,
        view: RoleView,
        schema: type[Record],
        repair: bool,
    ) -> ModelReply: ...


class OllamaModel:
    def __init__(self, base: str, model: str = MODEL, operator_model: str | None = None) -> None:
        self.base = base.rstrip("/")
        self.model = model
        self.operator_model = operator_model
        self.models: dict[str, ModelInfo] = {}
        self.lock = asyncio.Lock()

    async def model_info(self, model: str) -> ModelInfo:
        if model not in self.models:
            async with httpx.AsyncClient(base_url=self.base, timeout=10, trust_env=False) as http:
                response = await http.get("/api/tags")
                response.raise_for_status()
            for entry in response.json()["models"]:
                if entry["name"] == model:
                    self.models[model] = ModelInfo(model, str(entry["digest"]), 4096)
                    break
            if model not in self.models:
                raise ModelError(f"Pull {model} before selecting Ollama.")
        return self.models[model]

    async def info(self) -> ModelInfo:
        return await self.model_info(self.model)

    async def stage_info(self, stage: Stage) -> ModelInfo:
        name = self.operator_model if stage in {"operator", "operator_vnext"} else None
        return await self.model_info(name or self.model)

    async def generate(
        self,
        stage: Stage,
        view: RoleView,
        schema: type[Record],
        repair: bool,
    ) -> ModelReply:
        prompt = (PROMPT_DIR / f"{stage}.md").read_text()
        if "vnext_preferences" in view:
            prompt += (
                "\nUse the supplied preference_cost values. Lower values are better. "
                "Keep votes independent and use only the offer IDs provided."
            )
        if repair:
            prompt += "\nThe previous reply failed validation. Use only the output schema."
        info = await self.stage_info(stage)
        model = ChatOllama(
            model=info.name,
            base_url=self.base,
            temperature=0,
            seed=42,
            num_ctx=info.context,
            num_predict=260 if stage == "operator_vnext" else 130,
            reasoning=False,
            keep_alive="15m",
            client_kwargs={"timeout": 120, "trust_env": False},
            format=schema.model_json_schema(),
        )
        async with self.lock:
            message = await model.ainvoke(
                [("system", prompt), ("human", json.dumps(view, ensure_ascii=False))]
            )
        content = message.content
        if not isinstance(content, str):
            raise ModelError("Expected a JSON text response.")
        usage = message.usage_metadata
        return ModelReply(
            content, usage["input_tokens"] if usage else 0, usage["output_tokens"] if usage else 0
        )


class ReplayModel:
    def __init__(self, schedule: Schedule, fixture: Path | None = None) -> None:
        self.schedule = schedule
        path = fixture or DATA_ROOT / "fixtures" / "model_replays" / "demo.json"
        self.recording = path.read_bytes()
        self.frames = json.loads(self.recording)

    async def info(self) -> ModelInfo:
        return ModelInfo("replay", hashlib.sha256(self.recording).hexdigest(), 0)

    async def generate(
        self,
        stage: Stage,
        view: RoleView,
        schema: type[Record],
        repair: bool,
    ) -> ModelReply:
        frame = self.frames.get("recorded", {}).get(view_digest(stage, view))
        if frame is not None:
            return ModelReply(schema.model_validate(frame).model_dump_json(), 0, 0)
        if stage == "operator_vnext":
            return ModelReply(Extraction().model_dump_json(), 0, 0)
        if stage == "operator":
            notice = str(view["notice"])
            day = date.fromisoformat(str(view["day"]))
            incident = rule_notice(notice, self.schedule, day)
            parsed = replay_notice(incident)
            if notice == self.frames["notice"]:
                parsed = NoticeDecision.model_validate(self.frames["operator"])
            return ModelReply(parsed.model_dump_json(), 0, 0)

        pool = view["offers"]
        if not isinstance(pool, list) or not pool:
            raise ModelError("The role received no offers.")
        index = 1 if stage == "first" and view.get("rider") == "b" and len(pool) > 1 else 0
        row = pool[index]
        if not isinstance(row, dict):
            raise ModelError("The role received a malformed offer.")
        offer = str(view.get("proposed") or row["id"])
        if stage == "vote":
            output = Decision(offer=offer, action="accept", reason="valid")
        elif stage == "single":
            output = JointDecision(offer=offer, accept_a=True, accept_b=True)
        else:
            output = Choice(offer=offer, reason="earliest")
        return ModelReply(output.model_dump_json(), 0, 0)


def replay_notice(incident: Disruption | None) -> NoticeDecision:
    def stamp(second: int) -> str:
        return f"{second // 3600:02}:{second // 60 % 60:02}"

    if incident is None:
        return NoticeDecision(kind="clarify")
    if incident.kind == "stop_closure":
        return NoticeDecision(
            kind=incident.kind,
            stop=incident.stop,
            start=stamp(incident.start),
            end=stamp(incident.end),
        )
    if incident.kind == "trip_delay":
        return NoticeDecision(
            kind=incident.kind, trip=incident.trip, minutes=incident.seconds // 60
        )
    return NoticeDecision(kind=incident.kind, trip=incident.trip)


def parse_decision(decision: NoticeDecision, schedule: Schedule, day: date) -> Disruption | None:
    if decision.kind == "clarify":
        return None
    try:
        if decision.kind == "stop_closure":
            if (
                decision.stop not in schedule.stops
                or not decision.start
                or not decision.end
                or decision.trip is not None
                or decision.minutes is not None
            ):
                return None
            start = service_second(decision.start + ":00")
            end = service_second(decision.end + ":00")
            if end > 172800:
                return None
            return StopClosure(stop=decision.stop, start=start, end=end)
        if (
            decision.trip not in schedule.trips
            or decision.stop is not None
            or decision.start is not None
            or decision.end is not None
        ):
            return None
        trip = schedule.trips[decision.trip]
        if not schedule.runs(trip.service, day):
            return None
        if decision.kind == "trip_cancellation" and decision.minutes is None:
            return TripCancellation(trip=trip.id, service_date=day)
        if decision.kind == "trip_delay" and decision.minutes is not None:
            return TripDelay(trip=trip.id, service_date=day, seconds=decision.minutes * 60)
    except ValueError:
        return None
    return None


def view_for(
    stage: Stage,
    run: RunBody,
    schedule: Schedule,
    offers: tuple[Offer, ...] = (),
    *,
    rider: Rider | None = None,
    proposed: str | None = None,
    choices: tuple[str, ...] = (),
) -> RoleView:
    if stage == "operator":
        notice = run.notice or ""
        if run.clarification:
            notice = f"{notice}\nClarification: {run.clarification}"
        trips: list[JsonValue] = [trip for trip in schedule.trips if trip in notice]
        return {
            "notice": notice,
            "day": run.scenario.service_date.isoformat(),
            "stops": [[stop.id, stop.name] for stop in schedule.stops.values()],
            "trips": trips[:12],
        }
    if stage in {"first", "vote"}:
        if rider is None:
            raise ValueError("A rider role requires a rider identity.")
        routes: list[JsonValue] = []
        constraint = run.scenario.a if rider == "a" else run.scenario.b
        preference = run.preference_a if rider == "a" else run.preference_b
        for offer in offers:
            route = offer.a if rider == "a" else offer.b
            routes.append(
                {
                    "id": offer.id,
                    "arrival": route.arrival,
                    "meeting": offer.meeting,
                    "wait": offer.meeting - route.arrival,
                    "legs": len(route.legs),
                    "stop": route.destination,
                    **(
                        {"preference_cost": preference_cost(offer, rider, preference)}
                        if run.workflow == "vnext" and preference
                        else {}
                    ),
                }
            )
        result: RoleView = {
            "rider": rider,
            "constraints": constraint.model_dump(mode="json"),
            "offers": routes,
        }
        if run.workflow == "vnext" and preference:
            result["preference"] = preference
            result["vnext_preferences"] = True
        if stage == "vote":
            result["proposed"] = proposed
        return result
    pool: list[JsonValue] = []
    for offer in offers:
        if stage == "analyst":
            slack = [
                right.departure - left.arrival
                for route in (offer.a, offer.b)
                for left, right in zip(route.legs, route.legs[1:], strict=False)
                if left.kind == "walk"
            ]
            pool.append(
                {
                    "id": offer.id,
                    "meeting": offer.meeting,
                    "minimum_transfer_slack": min(slack) if slack else None,
                }
            )
        else:
            pool.append(
                {
                    "id": offer.id,
                    "meeting": offer.meeting,
                    "a_wait": offer.meeting - offer.a.arrival,
                    "b_wait": offer.meeting - offer.b.arrival,
                    "a_legs": len(offer.a.legs),
                    "b_legs": len(offer.b.legs),
                    **(
                        {
                            "a_preference_cost": preference_cost(offer, "a", run.preference_a),
                            "b_preference_cost": preference_cost(offer, "b", run.preference_b),
                        }
                        if run.workflow == "vnext" and stage == "single"
                        else {}
                    ),
                }
            )
    observed_choices: list[JsonValue] = [choice for choice in choices]
    result: RoleView = {"offers": pool, "choices": observed_choices}
    if run.workflow == "vnext" and stage == "single":
        result["vnext_preferences"] = True
    return result


def configured_model(schedule: Schedule) -> ModelPort:
    settings = get_settings()
    if settings.model == "ollama":
        return OllamaModel(settings.ollama_base_url, settings.ollama_model, settings.operator_model)
    return ReplayModel(schedule)
