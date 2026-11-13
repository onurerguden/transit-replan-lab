"""Check itineraries, joint plans and votes against the reference timetable."""

from trl.domain import Constraint, Itinerary, Leg, Offer, Ride, Scenario, Vote
from trl.verifier.occupancy import Presence, presence
from trl.verifier.reference import ReferenceTimetable
from trl.verifier.semantics import IncidentState

DAY = 86400
CLOSURE_CODES = {
    "walk": "closed_transfer",
    "alight": "closed_platform",
    "meeting": "closed_destination",
}


def _continuity(
    schedule: ReferenceTimetable, plan: Itinerary, constraint: Constraint
) -> str | None:
    stop, at = constraint.stop, constraint.ready
    for leg in plan.legs:
        if (
            leg.origin != stop
            or leg.departure < at
            or leg.arrival < leg.departure
            or leg.origin not in schedule.stops
            or leg.destination not in schedule.stops
        ):
            return "discontinuous_legs"
        stop, at = leg.destination, leg.arrival
    if stop != plan.destination or at != plan.arrival:
        return "arrival_mismatch"
    return None


def _accessibility(
    schedule: ReferenceTimetable, plan: Itinerary, constraint: Constraint
) -> str | None:
    if not constraint.accessible_only:
        return None
    stops = {constraint.stop, plan.destination}
    for leg in plan.legs:
        stops.update((leg.origin, leg.destination))
    if any(schedule.stops[stop].accessible is not True for stop in stops):
        return "unknown_stop_accessibility"
    return None


def _ride(
    schedule: ReferenceTimetable,
    scenario: Scenario,
    leg: Ride,
    incidents: IncidentState,
    constraint: Constraint,
) -> str | None:
    trip = schedule.trips.get(leg.trip)
    occurrence = (leg.trip, leg.service_date)
    if (
        trip is None
        or occurrence in incidents.cancellations
        or not schedule.runs(trip.service, leg.service_date)
    ):
        return "inactive_trip"
    if not 0 <= leg.board_index < leg.alight_index < len(trip.calls):
        return "invalid_call_indices"
    board, alight = trip.calls[leg.board_index], trip.calls[leg.alight_index]
    offset = (leg.service_date - scenario.service_date).days * DAY
    offset += incidents.delays.get(occurrence, 0)
    expected = (board.stop, board.departure + offset, alight.stop, alight.arrival + offset)
    if expected != (leg.origin, leg.departure, leg.destination, leg.arrival):
        return "timetable_mismatch"
    if not board.pickup or not alight.dropoff:
        return "timetable_mismatch"
    if constraint.accessible_only and trip.accessible is not True:
        return "unknown_trip_accessibility"
    return None


def _walk(
    schedule: ReferenceTimetable, leg: Leg, constraint: Constraint, previous_walk: bool
) -> tuple[str | None, int]:
    link = next(
        (
            item
            for item in schedule.transfers
            if item.origin == leg.origin and item.destination == leg.destination
        ),
        None,
    )
    if previous_walk or link is None or leg.arrival - leg.departure != link.duration:
        return "invalid_transfer", 0
    if constraint.accessible_only and link.accessible is not True:
        return "unknown_transfer_accessibility", 0
    return None, link.duration


def _closure(intervals: list[Presence], incidents: IncidentState) -> str | None:
    for item in intervals:
        if not incidents.occupied_while_closed(item.stop, item.first, item.last):
            continue
        if item.reason == "dwell":
            # Boarding inside a closure is a platform error; waiting through one is a dwell error.
            boarding = incidents.occupied_while_closed(item.stop, item.last, item.last)
            return "closed_platform" if boarding else "closed_dwell"
        return CLOSURE_CODES[item.reason]
    return None


def check_itinerary(
    schedule: ReferenceTimetable,
    scenario: Scenario,
    constraint: Constraint,
    plan: Itinerary,
    incidents: IncidentState,
    meeting: int | None = None,
) -> str | None:
    if plan.origin != constraint.stop or plan.start != constraint.ready:
        return "origin_mismatch"
    if plan.origin not in schedule.stops:
        return "unknown_origin"
    if plan.destination not in scenario.destinations or plan.destination not in schedule.stops:
        return "unknown_destination"
    if error := _continuity(schedule, plan, constraint) or _accessibility(
        schedule, plan, constraint
    ):
        return error
    rides = walking = 0
    previous_walk = False
    for leg in plan.legs:
        if leg.kind == "walk":
            error, duration = _walk(schedule, leg, constraint, previous_walk)
            walking += duration
        else:
            error = _ride(schedule, scenario, leg, incidents, constraint)
            rides += 1
        if error:
            return error
        previous_walk = leg.kind == "walk"
    if error := _closure(presence(constraint, plan, None), incidents):
        return error
    if (
        walking > constraint.walk_limit
        or rides > constraint.transfer_limit + 1
        or plan.arrival - plan.start > constraint.travel_limit
    ):
        return "rider_limit"
    return None


def check_plan(
    schedule: ReferenceTimetable, scenario: Scenario, offer: Offer, incidents: IncidentState
) -> str | None:
    for constraint, route in ((scenario.a, offer.a), (scenario.b, offer.b)):
        if error := check_itinerary(schedule, scenario, constraint, route, incidents):
            return error
    if offer.a.destination != offer.b.destination or not (
        max(offer.a.arrival, offer.b.arrival, scenario.meeting_start)
        <= offer.meeting
        <= min(
            offer.a.arrival + scenario.a.wait_limit,
            offer.b.arrival + scenario.b.wait_limit,
            scenario.meeting_end,
        )
    ):
        return "invalid_joint_arrival"
    for route in (offer.a, offer.b):
        waiting = Presence(route.destination, route.arrival, offer.meeting, "meeting")
        if error := _closure([waiting], incidents):
            return error
    return None


def verify_offer(
    schedule: ReferenceTimetable,
    scenario: Scenario,
    offer: Offer,
    votes: tuple[Vote, ...],
    version: int,
    incidents: IncidentState,
) -> str | None:
    if offer.version != version or {vote.rider for vote in votes} != {"a", "b"} or len(votes) != 2:
        return "missing_current_acceptances"
    if any(
        not vote.accepted or vote.offer_id != offer.id or vote.version != version for vote in votes
    ):
        return "missing_current_acceptances"
    return check_plan(schedule, scenario, offer, incidents)
