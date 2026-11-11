"""Departure-indexed connection search with separate labels for each arrival time."""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from heapq import heappop, heappush, nsmallest
from itertools import count

from trl.disruptions import Overlay
from trl.domain import Constraint, Itinerary, Leg, Offer, Ride, Scenario, Transfer, Trip, Walk
from trl.gtfs import Schedule

DAY = 86400
MAX_LABELS = 30_000


class SearchIncomplete(RuntimeError):
    """A bounded search exhausted its resource budget."""


@dataclass(frozen=True)
class Boarding:
    departure: int
    trip: Trip
    service_date: date
    index: int
    offset: int


@dataclass(frozen=True)
class Label:
    stop: str
    arrival: int
    rides: int
    walking: int
    legs: tuple[Leg, ...]

    @property
    def walked(self) -> bool:
        return bool(self.legs and self.legs[-1].kind == "walk")


def connections(
    schedule: Schedule, day: date, overlay: Overlay, start: int, end: int
) -> dict[str, list[Boarding]]:
    result: dict[str, list[Boarding]] = defaultdict(list)
    for trip in schedule.trips.values():
        earliest = (start - trip.calls[-1].arrival - 43200) // DAY
        latest = (end - trip.calls[0].departure) // DAY
        for shift in range(earliest, latest + 1):
            actual = day + timedelta(days=shift)
            key = (trip.id, actual)
            if key in overlay.cancellations or not schedule.runs(trip.service, actual):
                continue
            offset = shift * DAY + overlay.delays.get(key, 0)
            for index, call in enumerate(trip.calls[:-1]):
                departure = call.departure + offset
                if (
                    call.pickup
                    and start <= departure <= end
                    and not overlay.closed(call.stop, departure)
                ):
                    result[call.stop].append(Boarding(departure, trip, actual, index, offset))
    for departures in result.values():
        departures.sort(key=lambda item: (item.departure, item.trip.id, item.index))
    return dict(result)


def alternatives(
    schedule: Schedule,
    index: dict[str, list[Boarding]],
    constraint: Constraint,
    destinations: tuple[str, ...],
    deadline: int,
    overlay: Overlay,
) -> list[Label]:
    earliest = constraint.ready
    latest = min(deadline, earliest + constraint.travel_limit)
    if earliest > latest or not accessible(schedule, constraint, constraint.stop):
        return []
    serial = count()
    pending: list[tuple[int, int, Label]] = []
    frontier: dict[tuple[str, int, bool], list[tuple[int, int]]] = defaultdict(list)
    transfers: dict[str, list[Transfer]] = defaultdict(list)
    for transfer in schedule.transfers:
        transfers[transfer.origin].append(transfer)
    final: list[Label] = []
    accepted = 0

    def add(label: Label) -> None:
        nonlocal accepted
        key = (label.stop, label.arrival, label.walked)
        costs = frontier[key]
        if any(r <= label.rides and w <= label.walking for r, w in costs):
            return
        costs[:] = [(r, w) for r, w in costs if not (label.rides <= r and label.walking <= w)]
        costs.append((label.rides, label.walking))
        accepted += 1
        if accepted > MAX_LABELS:
            raise SearchIncomplete("Arrival label budget exhausted.")
        heappush(pending, (label.arrival, next(serial), label))

    add(Label(constraint.stop, earliest, 0, 0, ()))
    while pending:
        _, _, current = heappop(pending)
        costs = frontier[current.stop, current.arrival, current.walked]
        if (current.rides, current.walking) not in costs:
            continue
        if current.stop in destinations:
            final.append(current)
        for walk in transfers[current.stop] if not current.walked else ():
            departure = overlay.first_open_walk(
                walk.origin, walk.destination, current.arrival, walk.duration
            )
            arrival = departure + walk.duration
            walking = current.walking + walk.duration
            if (
                arrival <= latest
                and walking <= constraint.walk_limit
                and (not constraint.accessible_only or walk.accessible is True)
                and accessible(schedule, constraint, walk.destination)
            ):
                leg = Walk(
                    origin=walk.origin,
                    destination=walk.destination,
                    departure=departure,
                    arrival=arrival,
                )
                add(Label(walk.destination, arrival, current.rides, walking, (*current.legs, leg)))
        if current.rides >= constraint.transfer_limit + 1:
            continue
        departures = index.get(current.stop, [])
        first = bisect_left(departures, current.arrival, key=lambda item: item.departure)
        for connection in departures[first:]:
            if connection.departure > latest:
                break
            if constraint.accessible_only and connection.trip.accessible is not True:
                continue
            for alight in range(connection.index + 1, len(connection.trip.calls)):
                call = connection.trip.calls[alight]
                arrival = call.arrival + connection.offset
                if arrival > latest:
                    break
                if (
                    call.dropoff
                    and accessible(schedule, constraint, call.stop)
                    and not overlay.closed(call.stop, arrival)
                ):
                    leg = Ride(
                        origin=current.stop,
                        destination=call.stop,
                        departure=connection.departure,
                        arrival=arrival,
                        trip=connection.trip.id,
                        service_date=connection.service_date,
                        board_index=connection.index,
                        alight_index=alight,
                    )
                    add(
                        Label(
                            call.stop,
                            arrival,
                            current.rides + 1,
                            current.walking,
                            (*current.legs, leg),
                        )
                    )
    return final


def accessible(schedule: Schedule, constraint: Constraint, stop: str) -> bool:
    return stop in schedule.stops and (
        not constraint.accessible_only or schedule.stops[stop].accessible is True
    )


def itinerary(label: Label, constraint: Constraint) -> Itinerary:
    return Itinerary(
        origin=constraint.stop,
        destination=label.stop,
        start=constraint.ready,
        arrival=label.arrival,
        legs=label.legs,
    )


def leg_key(legs: tuple[Leg, ...]) -> tuple[tuple[str, str, int, str, int], ...]:
    return tuple(
        (
            leg.origin,
            leg.destination,
            leg.departure,
            leg.trip if leg.kind == "ride" else "",
            leg.board_index if leg.kind == "ride" else -1,
        )
        for leg in legs
    )


def find_offers(
    schedule: Schedule,
    scenario: Scenario,
    version: int = 0,
    overlay: Overlay | None = None,
    limit: int = 6,
) -> list[Offer]:
    overlay = overlay or Overlay.compile(())
    index = connections(
        schedule,
        scenario.service_date,
        overlay,
        min(scenario.a.ready, scenario.b.ready),
        min(
            scenario.meeting_end,
            max(
                scenario.a.ready + scenario.a.travel_limit,
                scenario.b.ready + scenario.b.travel_limit,
            ),
        ),
    )
    a = alternatives(
        schedule, index, scenario.a, scenario.destinations, scenario.meeting_end, overlay
    )
    b = alternatives(
        schedule, index, scenario.b, scenario.destinations, scenario.meeting_end, overlay
    )
    b_by_stop: dict[str, list[Label]] = defaultdict(list)
    for label in b:
        b_by_stop[label.stop].append(label)

    def rank(pair: tuple[Label, Label, int]) -> tuple[object, ...]:
        left, right, meeting = pair
        return (
            meeting,
            max(left.arrival - scenario.a.ready, right.arrival - scenario.b.ready),
            max(0, left.rides - 1) + max(0, right.rides - 1),
            left.walking + right.walking,
            left.stop,
            leg_key(left.legs),
            leg_key(right.legs),
        )

    pairs = (
        (left, right, meeting)
        for left in a
        for right in b_by_stop[left.stop]
        if (meeting := max(left.arrival, right.arrival, scenario.meeting_start))
        <= min(
            scenario.meeting_end,
            left.arrival + scenario.a.wait_limit,
            right.arrival + scenario.b.wait_limit,
        )
        and not overlay.closed(left.stop, min(left.arrival, right.arrival), meeting)
    )
    return [
        Offer(
            id=f"v{version}-{number}",
            version=version,
            a=itinerary(left, scenario.a),
            b=itinerary(right, scenario.b),
            meeting=meeting,
        )
        for number, (left, right, meeting) in enumerate(nsmallest(limit, pairs, key=rank), start=1)
    ]
