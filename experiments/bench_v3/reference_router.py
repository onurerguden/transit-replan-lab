# pyright: basic
"""A second router for plan labels: time-dependent Dijkstra over stops.

It shares no search code with `trl.routing`. It ignores transfer, walk and wait limits and
closures, so its earliest meeting is a lower bound that the label search must never beat and
should match when those limits are loose.
"""

import heapq
from datetime import date, timedelta

from trl.domain import Scenario
from trl.gtfs import Schedule

DAY = 86400


def earliest(
    schedule: Schedule, day: date, origin: str, ready: int, horizon: int
) -> dict[str, int]:
    departures: dict[str, list[tuple[int, str, int, int]]] = {}
    for trip in schedule.trips.values():
        for shift in (-1, 0, 1):
            if not schedule.runs(trip.service, day + timedelta(days=shift)):
                continue
            for index, call in enumerate(trip.calls[:-1]):
                if call.pickup:
                    departures.setdefault(call.stop, []).append(
                        (call.departure + shift * DAY, trip.id, index, shift)
                    )
    for entries in departures.values():
        entries.sort()
    walks: dict[str, list[tuple[str, int]]] = {}
    for link in schedule.transfers:
        walks.setdefault(link.origin, []).append((link.destination, link.duration))
    best = {origin: ready}
    queue = [(ready, origin)]
    while queue:
        at, stop = heapq.heappop(queue)
        if at > best.get(stop, 1 << 60) or at > horizon:
            continue
        for destination, duration in walks.get(stop, ()):
            if at + duration < best.get(destination, 1 << 60):
                best[destination] = at + duration
                heapq.heappush(queue, (at + duration, destination))
        for departure, trip_id, index, shift in departures.get(stop, ()):
            if departure < at:
                continue
            if departure > horizon:
                break
            trip = schedule.trips[trip_id]
            for call in trip.calls[index + 1 :]:
                arrival = call.arrival + shift * DAY
                if call.dropoff and arrival < best.get(call.stop, 1 << 60):
                    best[call.stop] = arrival
                    heapq.heappush(queue, (arrival, call.stop))
    return best


def earliest_meeting(schedule: Schedule, scenario: Scenario) -> int | None:
    horizon = scenario.meeting_end
    a = earliest(
        schedule, scenario.service_date, scenario.a.stop, scenario.a.ready, horizon
    )
    b = earliest(
        schedule, scenario.service_date, scenario.b.stop, scenario.b.ready, horizon
    )
    options = [
        max(a[d], b[d], scenario.meeting_start)
        for d in scenario.destinations
        if d in a and d in b
    ]
    meeting = min(options, default=None)
    return meeting if meeting is not None and meeting <= scenario.meeting_end else None
