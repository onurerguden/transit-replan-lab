"""Versioned evidence shared by the API, simulation, and durable run state."""

from typing import Annotated, Literal

from pydantic import Field

from trl.domain import Disruption, Offer, Record, Rider, Second

Workflow = Literal["legacy", "vnext"]
OperatorMode = Literal["rules", "hybrid"]
RoutePolicy = Literal["earliest", "robust", "balanced"]
Preference = Literal["fewer_transfers", "less_wait", "less_walking", "earlier_arrival"]
Slot = Literal["target", "kind", "start", "end", "delay"]
IncidentKind = Literal["stop_closure", "trip_cancellation", "trip_delay"]


class Span(Record):
    source: Literal["notice", "answer"]
    start: Second
    end: Second


class Fact(Record):
    slot: Slot
    value: str | int
    span: Span | None = None


class ExtractionQuote(Record):
    slot: Slot
    quote: Annotated[str, Field(min_length=1, max_length=200)]


class Extraction(Record):
    quotes: Annotated[tuple[ExtractionQuote, ...], Field(max_length=6)] = ()


class Hypothesis(Record):
    id: str
    incident: Disruption
    facts: tuple[Fact, ...]


class Impact(Record):
    hypothesis: Hypothesis
    status: Literal["feasible", "infeasible", "search_incomplete"]
    preview: Offer | None = None


class Option(Record):
    id: str
    value: str | int
    label: str


class Question(Record):
    id: str
    slot: Slot
    prompt: str
    options: tuple[Option, ...] = ()


class Intake(Record):
    action: Literal["apply", "ask", "abstain"]
    facts: tuple[Fact, ...]
    reasons: tuple[str, ...] = ()
    selected: Hypothesis | None = None
    impacts: tuple[Impact, ...] = ()
    question: Question | None = None


class Counterfactual(Record):
    trip: str
    extra_seconds: int = 120
    meeting: Second | None = None
    failure: str | None = None


class OfferEvidence(Record):
    offer_id: str
    policies: tuple[RoutePolicy, ...]
    successful: Second
    total: Second
    transfer_slack: int | None
    extra_seconds_a: int | None
    extra_seconds_b: int | None
    counterfactual: Counterfactual | None


class RunEvidence(Record):
    snapshot: str
    scenario_profile: str
    operator_mode: OperatorMode = "rules"
    intake: Intake | None = None
    offers: tuple[OfferEvidence, ...] = ()
    notice_text: str | None = None
    answer_text: str | None = None


def preference_cost(offer: Offer, rider: Rider, preference: Preference | None) -> int:
    route = offer.a if rider == "a" else offer.b
    if preference == "earlier_arrival":
        return route.arrival
    if preference == "fewer_transfers":
        return max(0, sum(leg.kind == "ride" for leg in route.legs) - 1)
    if preference == "less_wait":
        return offer.meeting - route.arrival
    if preference == "less_walking":
        return sum(leg.arrival - leg.departure for leg in route.legs if leg.kind == "walk")
    return 0


def preferred_offer(
    offers: tuple[Offer, ...], preference_a: Preference | None, preference_b: Preference | None
) -> Offer:
    preferences: tuple[tuple[Rider, Preference | None], ...] = (
        ("a", preference_a),
        ("b", preference_b),
    )
    ranks = {
        rider: {
            cost: index
            for index, cost in enumerate(
                sorted({preference_cost(offer, rider, preference) for offer in offers})
            )
        }
        for rider, preference in preferences
    }

    def rank(offer: Offer) -> int:
        return (
            ranks["a"][preference_cost(offer, "a", preference_a)]
            + ranks["b"][preference_cost(offer, "b", preference_b)]
        )

    return min(offers, key=rank)
