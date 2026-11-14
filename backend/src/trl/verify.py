"""Adapt router-side overlays to the independent verifier.

The adapter copies the compiled incident data only. Closure semantics live in
`trl.verifier.semantics` and never call the overlay's own methods.
"""

from trl.disruptions import Overlay
from trl.domain import Constraint, Itinerary, Offer, Scenario, Vote
from trl.gtfs import Schedule
from trl.verifier import check as independent
from trl.verifier.semantics import IncidentState


def incidents(overlay: Overlay) -> IncidentState:
    return IncidentState(
        closures={stop: list(spans) for stop, spans in overlay.closures.items()},
        cancellations=frozenset(overlay.cancellations),
        delays=dict(overlay.delays),
    )


def check_itinerary(
    schedule: Schedule,
    scenario: Scenario,
    constraint: Constraint,
    plan: Itinerary,
    overlay: Overlay,
) -> str | None:
    return independent.check_itinerary(schedule, scenario, constraint, plan, incidents(overlay))


def check_plan(
    schedule: Schedule, scenario: Scenario, offer: Offer, overlay: Overlay
) -> str | None:
    return independent.check_plan(schedule, scenario, offer, incidents(overlay))


def verify_offer(
    schedule: Schedule,
    scenario: Scenario,
    offer: Offer,
    votes: tuple[Vote, ...],
    version: int,
    overlay: Overlay,
) -> str | None:
    return independent.verify_offer(schedule, scenario, offer, votes, version, incidents(overlay))
