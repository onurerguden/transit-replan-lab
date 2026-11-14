"""Commands and the public read model."""

import hashlib
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
    # `add` keeps earlier incidents active. `replace` retracts them before reading the report.
    mode: Literal["add", "replace"] = "add"


class Retract(Record):
    version: Second
    incident_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=8)]


class Retry(Record):
    version: Second


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
    # Set by a retraction: the remaining incidents stand, so the worker skips report intake.
    skip_intake: bool = False


def incident_id(incident: Disruption) -> str:
    return hashlib.sha256(incident.model_dump_json().encode()).hexdigest()[:12]


class IncidentView(Record):
    id: str
    disruption: Disruption


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
    incidents: tuple[IncidentView, ...] = ()
    retryable: bool = False


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


class RouteQuery(Record):
    """A stateless meeting query on the compiled network."""

    a_stop: str
    b_stop: str
    destination: str
    a_ready: Second
    b_ready: Second
    wait_limit: Annotated[int, Field(ge=0, le=7200)] = 600
    meeting_start: Second | None = None
    meeting_end: Annotated[int, Field(gt=0, le=172800)] | None = None
    limit: Annotated[int, Field(ge=1, le=6)] = 3
    # Exact search keeps every alternative chain. The default dominates across arrival times.
    exact: bool = False


class RouteAnswer(Record):
    network: Literal["core", "full"]
    mode: Literal["fast", "exact"] = "fast"
    status: Literal["feasible", "infeasible", "search_incomplete"]
    offers: tuple[Offer, ...] = ()
    kept_trips: int = 0
    work: int = 0
    detail: str | None = None
