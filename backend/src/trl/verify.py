"""Verify submitted plans directly against the immutable timetable and votes."""

from trl.disruptions import Overlay
from trl.domain import Constraint, Itinerary, Offer, Scenario, Vote
from trl.gtfs import Schedule


def check_itinerary(
    schedule: Schedule,
    scenario: Scenario,
    constraint: Constraint,
    plan: Itinerary,
    overlay: Overlay,
) -> str | None:
    if plan.origin != constraint.stop or plan.start != constraint.ready:
        return "origin_mismatch"
    if plan.origin not in schedule.stops:
        return "unknown_origin"
    if plan.destination not in scenario.destinations or plan.destination not in schedule.stops:
        return "unknown_destination"
    stop, at = constraint.stop, constraint.ready
    rides = walking = 0
    last_walk = False
    for leg in plan.legs:
        if (
            leg.origin != stop
            or leg.departure < at
            or leg.arrival < leg.departure
            or leg.origin not in schedule.stops
            or leg.destination not in schedule.stops
        ):
            return "discontinuous_legs"
        if constraint.accessible_only and (
            schedule.stops[leg.origin].accessible is not True
            or schedule.stops[leg.destination].accessible is not True
        ):
            return "unknown_stop_accessibility"
        if leg.kind == "walk":
            link = next(
                (
                    item
                    for item in schedule.transfers
                    if item.origin == stop and item.destination == leg.destination
                ),
                None,
            )
            if last_walk or link is None or leg.arrival - leg.departure != link.duration:
                return "invalid_transfer"
            if constraint.accessible_only and link.accessible is not True:
                return "unknown_transfer_accessibility"
            if overlay.closed(stop, leg.departure, leg.arrival) or overlay.closed(
                leg.destination, leg.departure, leg.arrival
            ):
                return "closed_transfer"
            walking += link.duration
        else:
            trip = schedule.trips.get(leg.trip)
            key = (leg.trip, leg.service_date)
            if (
                trip is None
                or key in overlay.cancellations
                or not schedule.runs(trip.service, leg.service_date)
            ):
                return "inactive_trip"
            if not 0 <= leg.board_index < leg.alight_index < len(trip.calls):
                return "invalid_call_indices"
            board, alight = trip.calls[leg.board_index], trip.calls[leg.alight_index]
            shift = (leg.service_date - scenario.service_date).days * 86400
            shift += overlay.delays.get(key, 0)
            if (
                (board.stop, board.departure + shift, alight.stop, alight.arrival + shift)
                != (leg.origin, leg.departure, leg.destination, leg.arrival)
                or not board.pickup
                or not alight.dropoff
            ):
                return "timetable_mismatch"
            if overlay.closed(board.stop, leg.departure) or overlay.closed(
                alight.stop, leg.arrival
            ):
                return "closed_platform"
            if constraint.accessible_only and trip.accessible is not True:
                return "unknown_trip_accessibility"
            rides += 1
        last_walk = leg.kind == "walk"
        stop, at = leg.destination, leg.arrival
    if constraint.accessible_only and schedule.stops[stop].accessible is not True:
        return "unknown_stop_accessibility"
    if stop != plan.destination or at != plan.arrival:
        return "arrival_mismatch"
    if (
        walking > constraint.walk_limit
        or rides > constraint.transfer_limit + 1
        or at - plan.start > constraint.travel_limit
    ):
        return "rider_limit"
    return None


def verify_offer(
    schedule: Schedule,
    scenario: Scenario,
    offer: Offer,
    votes: tuple[Vote, ...],
    version: int,
    overlay: Overlay,
) -> str | None:
    if offer.version != version or {vote.rider for vote in votes} != {"a", "b"} or len(votes) != 2:
        return "missing_current_acceptances"
    if any(
        not vote.accepted or vote.offer_id != offer.id or vote.version != version for vote in votes
    ):
        return "missing_current_acceptances"
    return check_plan(schedule, scenario, offer, overlay)


def check_plan(
    schedule: Schedule, scenario: Scenario, offer: Offer, overlay: Overlay
) -> str | None:
    for constraint, route in ((scenario.a, offer.a), (scenario.b, offer.b)):
        if error := check_itinerary(schedule, scenario, constraint, route, overlay):
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
    if overlay.closed(offer.a.destination, min(offer.a.arrival, offer.b.arrival), offer.meeting):
        return "closed_destination"
    return None
