"""Commands and the public read model."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue

from trl.domain import Architecture, Disruption, Offer, Record, Scenario, Second, Status, Stop, Vote


class CreateRun(Record):
    scenario: Literal["demo", "infeasible"] = "demo"
    architecture: Architecture = "rules"
    counteroffers: bool = True


class Disrupt(Record):
    version: Second
    notice: Annotated[str, Field(min_length=1, max_length=600)]


class Clarify(Record):
    version: Second
    answer: Annotated[str, Field(min_length=1, max_length=400)]


class Receipt(Record):
    run_id: str
    version: Second


class RunBody(Record):
    id: str
    version: Second = 0
    architecture: Architecture
    counteroffers: bool
    scenario: Scenario
    status: Status = "ready"
    initial: Offer | None
    incident: Disruption | None = None
    overlays: tuple[Disruption, ...] = ()
    notice: str | None = None
    clarification: str | None = None
    question: str | None = None
    verified_offer: str | None = None
    error: str | None = None


class RunView(Record):
    id: str
    version: Second
    status: Status
    architecture: Architecture
    service_date: str
    scenario: str
    notice: str
    origin_a: str
    origin_b: str
    destinations: tuple[str, ...]
    initial: Offer | None
    incident: Disruption | None
    offers: tuple[Offer, ...]
    votes: tuple[Vote, ...]
    question: str | None
    verified_offer: str | None
    error: str | None


class EventDraft(Record):
    kind: str
    role: str
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class Event(EventDraft):
    seq: int
    version: int
    recorded_at: str


class RouteLine(Record):
    id: str
    mode: Literal["metro", "tram"]
    stops: tuple[str, ...]


class Network(Record):
    stops: tuple[Stop, ...]
    lines: tuple[RouteLine, ...]
