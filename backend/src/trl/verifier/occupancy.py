"""List where and when a rider is present at a stop."""

from dataclasses import dataclass

from trl.domain import Constraint, Itinerary


@dataclass(frozen=True)
class Presence:
    stop: str
    first: int
    last: int
    reason: str


def presence(constraint: Constraint, plan: Itinerary, meeting: int | None) -> list[Presence]:
    """Return inclusive presence intervals. Riding through a stop is not presence."""
    intervals: list[Presence] = []
    stop, at = constraint.stop, constraint.ready
    for leg in plan.legs:
        intervals.append(Presence(stop, at, leg.departure, "dwell"))
        if leg.kind == "walk":
            intervals.append(Presence(leg.origin, leg.departure, leg.arrival, "walk"))
            intervals.append(Presence(leg.destination, leg.departure, leg.arrival, "walk"))
        else:
            intervals.append(Presence(leg.destination, leg.arrival, leg.arrival, "alight"))
        stop, at = leg.destination, leg.arrival
    if meeting is not None:
        intervals.append(Presence(stop, at, meeting, "meeting"))
    return intervals
