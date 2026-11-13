"""Departure-indexed connection search with separate labels for each arrival time."""

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import date, timedelta
from heapq import heappop, heappush, nsmallest
from itertools import count

from trl.disruptions import Overlay
from trl.domain import Constraint, Itinerary, Leg, Offer, Ride, Scenario, Transfer, Trip, Walk
from trl.gtfs import Schedule

DAY = 86400
MAX_LABELS = 30_000
MAX_PAIRS = 500_000


class SearchIncomplete(RuntimeError):
    """A bounded search exhausted its resource budget."""


@dataclass
class SearchStats:
    labels: int = 0
    pairs: int = 0


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


@dataclass(frozen=True)
class ArrivalWindow:
    first: Label
    last: int
    open_until: int

    def meeting_deadline(self, wait_limit: int) -> int:
        return min(self.last + wait_limit, self.open_until)

    def at_meeting(self, meeting: int, wait_limit: int) -> Label:
        arrival = max(self.first.arrival, meeting - wait_limit)
        if arrival == self.first.arrival:
            return self.first
        walk = self.first.legs[-1]
        if walk.kind != "walk":
            raise ValueError("A shifted meeting arrival requires a final walk.")
        leg = walk.model_copy(
            update={"departure": walk.departure + arrival - walk.arrival, "arrival": arrival}
        )
        return replace(self.first, arrival=arrival, legs=(*self.first.legs[:-1], leg))


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
    *,
    margin_aware: bool = False,
    stats: SearchStats | None = None,
) -> list[ArrivalWindow]:
    earliest = constraint.ready
    latest = min(deadline, earliest + constraint.travel_limit)
    if earliest > latest or not accessible(schedule, constraint, constraint.stop):
        return []
    serial = count()
    pending: list[tuple[int, int, Label]] = []
    frontier: dict[tuple[str, int, bool], list[tuple[int, int, int]]] = defaultdict(list)
    transfers: dict[str, list[Transfer]] = defaultdict(list)
    for transfer in schedule.transfers:
        transfers[transfer.origin].append(transfer)
    final: list[ArrivalWindow] = []
    accepted = 0

    def cost(label: Label) -> tuple[int, int, int]:
        # Preserve a larger transfer margin at equal arrival and resource cost.
        # This remains a bounded candidate heuristic, not a stochastic optimum.
        margin = transfer_margin(label.legs) if margin_aware else None
        return label.rides, label.walking, -margin[0] if margin else -86400

    def dominates(left: tuple[int, int, int], right: tuple[int, int, int]) -> bool:
        return left[0] <= right[0] and left[1] <= right[1] and left[2] <= right[2]

    def finish(label: Label, last: int) -> None:
        until = overlay.last_open_second(label.stop, label.arrival, deadline)
        if until >= label.arrival:
            final.append(ArrivalWindow(label, min(last, until), until))
        if len(final) > MAX_LABELS:
            raise SearchIncomplete("Arrival window budget exhausted.")

    def add(label: Label) -> None:
        nonlocal accepted
        key = (label.stop, label.arrival, label.walked)
        costs = frontier[key]
        candidate = cost(label)
        if any(dominates(old, candidate) for old in costs):
            return
        costs[:] = [old for old in costs if not dominates(candidate, old)]
        costs.append(candidate)
        accepted += 1
        if stats is not None:
            stats.labels += 1
        if accepted > MAX_LABELS:
            raise SearchIncomplete("Arrival label budget exhausted.")
        heappush(pending, (label.arrival, next(serial), label))

    add(Label(constraint.stop, earliest, 0, 0, ()))
    while pending:
        _, _, current = heappop(pending)
        costs = frontier[current.stop, current.arrival, current.walked]
        if cost(current) not in costs:
            continue
        if current.stop in destinations and not current.walked:
            finish(current, current.arrival)
        for walk in transfers[current.stop] if not current.walked else ():
            walking = current.walking + walk.duration
            if (
                walking > constraint.walk_limit
                or (constraint.accessible_only and walk.accessible is not True)
                or not accessible(schedule, constraint, walk.destination)
            ):
                continue
            windows = overlay.walk_windows(
                walk.origin,
                walk.destination,
                current.arrival,
                latest - walk.duration,
                walk.duration,
            )
            for index_in_walk, (departure, end) in enumerate(windows):
                arrival = departure + walk.duration
                leg = Walk(
                    origin=walk.origin,
                    destination=walk.destination,
                    departure=departure,
                    arrival=arrival,
                )
                label = Label(
                    walk.destination, arrival, current.rides, walking, (*current.legs, leg)
                )
                if index_in_walk == 0:
                    # Earlier arrival can board any onward connection a later walk can reach.
                    add(label)
                if walk.destination in destinations:
                    finish(label, end + walk.duration)
                else:
                    break
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
    *,
    diverse: bool = False,
    initial: Offer | None = None,
    margin_aware: bool = False,
    stats: SearchStats | None = None,
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
        schedule,
        index,
        scenario.a,
        scenario.destinations,
        scenario.meeting_end,
        overlay,
        margin_aware=margin_aware,
        stats=stats,
    )
    b = alternatives(
        schedule,
        index,
        scenario.b,
        scenario.destinations,
        scenario.meeting_end,
        overlay,
        margin_aware=margin_aware,
        stats=stats,
    )
    b_by_stop: dict[str, list[ArrivalWindow]] = defaultdict(list)
    for window in sorted(b, key=lambda item: item.first.arrival):
        b_by_stop[window.first.stop].append(window)

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

    def pairs() -> Iterator[tuple[Label, Label, int]]:
        examined = 0
        for left in a:
            deadline = left.meeting_deadline(scenario.a.wait_limit)
            for right in b_by_stop[left.first.stop]:
                if right.first.arrival > deadline:
                    break
                examined += 1
                if stats is not None:
                    stats.pairs += 1
                if examined > MAX_PAIRS:
                    raise SearchIncomplete("Joint arrival pair budget exhausted.")
                meeting = max(left.first.arrival, right.first.arrival, scenario.meeting_start)
                if meeting <= min(deadline, right.meeting_deadline(scenario.b.wait_limit)):
                    yield (
                        left.at_meeting(meeting, scenario.a.wait_limit),
                        right.at_meeting(meeting, scenario.b.wait_limit),
                        meeting,
                    )

    if diverse:
        selected = diverse_pairs(pairs(), rank, initial, scenario)
    else:
        selected = nsmallest(limit, pairs(), key=rank)
    return [
        Offer(
            id=f"v{version}-{number}",
            version=version,
            a=itinerary(left, scenario.a),
            b=itinerary(right, scenario.b),
            meeting=meeting,
        )
        for number, (left, right, meeting) in enumerate(selected, start=1)
    ]


Pair = tuple[Label, Label, int]


def trip_chain(legs: tuple[Leg, ...]) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        (
            leg.kind,
            leg.origin,
            leg.destination,
            f"{leg.trip}:{leg.service_date}" if leg.kind == "ride" else "",
        )
        for leg in legs
    )


def transfer_margin(legs: tuple[Leg, ...]) -> tuple[int, Ride] | None:
    previous: Ride | None = None
    walking = 0
    tightest: tuple[int, Ride] | None = None
    for leg in legs:
        if leg.kind == "walk":
            walking += leg.arrival - leg.departure
            continue
        if previous:
            slack = leg.departure - previous.arrival - walking
            if tightest is None or slack < tightest[0]:
                tightest = slack, previous
        previous, walking = leg, 0
    return tightest


def diverse_pairs(
    candidates: Iterator[Pair],
    rank: Callable[[Pair], tuple[object, ...]],
    initial: Offer | None,
    scenario: Scenario,
) -> list[Pair]:
    pools: list[dict[object, tuple[tuple[object, ...], Pair]]] = [{}, {}, {}]
    for pair in candidates:
        a, b, _ = pair
        base = rank(pair)
        margins = [item[0] for route in (a, b) if (item := transfer_margin(route.legs))]
        robustness = -min(margins) if margins else -86400
        if initial is None:
            burden = max(a.arrival - scenario.a.ready, b.arrival - scenario.b.ready)
        else:
            burden = max(a.arrival - initial.a.arrival, b.arrival - initial.b.arrival)
        signature = trip_chain(a.legs), trip_chain(b.legs)
        for pool, order in zip(pools, (base, (robustness, *base), (burden, *base)), strict=True):
            current = pool.get(signature)
            if current is not None:
                if order < current[0]:  # pyright: ignore[reportOperatorIssue]
                    pool[signature] = order, pair
                continue
            if len(pool) == 8:
                worst = max(pool, key=lambda key: pool[key][0])
                if order >= pool[worst][0]:  # pyright: ignore[reportOperatorIssue]
                    continue
                del pool[worst]
            pool[signature] = order, pair
    selected: dict[object, Pair] = {}
    for pool in pools:
        for signature, (_, pair) in sorted(pool.items(), key=lambda row: row[1][0]):
            selected.setdefault(signature, pair)
    return list(selected.values())
