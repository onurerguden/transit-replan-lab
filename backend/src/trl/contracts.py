"""Commands and the public read model."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, model_validator

from trl.domain import Architecture, Disruption, Offer, Record, Scenario, Second, Status, Stop, Vote
from trl.vnext import OperatorMode, Preference, RoutePolicy, RunEvidence, Workflow


class CreateRun(Record):
    scenario: Literal["demo", "infeasible", "resilience"] = "demo"
    architecture: Architecture = "rules"
    counteroffers: bool = True
    workflow: Workflow = "legacy"
    operator_mode: OperatorMode | None = None
    route_policy: RoutePolicy = "earliest"
    preference_a: Preference | None = None
    preference_b: Preference | None = None


class Disrupt(Record):
    version: Second
    notice: Annotated[str, Field(min_length=1, max_length=600)]


class Clarify(Record):
    version: Second
    answer: Annotated[str, Field(min_length=1, max_length=400)] | None = None
    question_id: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    option_id: Annotated[str, Field(min_length=1, max_length=32)] | None = None

    @model_validator(mode="after")
    def answer_or_option(self) -> "Clarify":
        if (self.answer is None) == (self.option_id is None):
            raise ValueError("Provide exactly one answer or option.")
        return self


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
    workflow: Workflow = "legacy"
    operator_mode: OperatorMode = "rules"
    route_policy: RoutePolicy = "earliest"
    preference_a: Preference | None = None
    preference_b: Preference | None = None
    evidence: RunEvidence | None = None
    clarification_option: str | None = None
    notice: str | None = None
    clarification: str | None = None
    question: str | None = None
    verified_offer: str | None = None
    error: str | None = None


class ModelCall(Record):
    id: int
    step: str
    model: str
    digest: str
    context: int
    request_sha256: str
    state: str
    content: str | None
    input_tokens: int
    output_tokens: int
    duration_ms: int


class Metrics(Record):
    backend: Literal["none", "replay", "ollama"] = "none"
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_ms: int = 0


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
    metrics: Metrics
    evidence: RunEvidence | None = None


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
