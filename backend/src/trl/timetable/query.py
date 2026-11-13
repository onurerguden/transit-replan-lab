# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Answer one meeting query on the compiled network by bounding it first.

Two vectorized passes bound what can matter. A forward pass finds the earliest each rider can
reach every stop, a backward pass finds the latest they can leave a stop and still reach a
destination by the deadline. Both ignore closures, cancellations and accessibility, which only
remove options, and include delays, which can add some. A trip that cannot lie on any journey
is dropped. The exact search then runs on the small remaining schedule, so its answer equals
the answer on the full network.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from numpy.typing import NDArray

from trl.disruptions import Overlay
from trl.domain import Offer, Scenario, Stop, StopTime, Transfer, Trip
from trl.gtfs import Schedule, Service
from trl.routing import Budget, SearchStats, find_offers
from trl.timetable.compact import CompactTimetable
from trl.timetable.footpaths import Footpaths

DAY = 86400
NEVER = np.int32(2**30)
SHIFTS = (-1, 0, 1)


@dataclass(frozen=True)
class Window:
    schedule: Schedule
    occurrences: int
    rows: int
    kept_trips: int
    lower_bound: int = 0


@dataclass(frozen=True)
class Rows:
    """Stop-time rows of every active trip occurrence inside the query window."""

    trip: NDArray[np.int64]
    shift: NDArray[np.int64]
    stop: NDArray[np.int32]
    arr: NDArray[np.int64]
    dep: NDArray[np.int64]
    pickup: NDArray[np.bool_]
    dropoff: NDArray[np.bool_]
    first: NDArray[np.intp]
    rank: NDArray[np.int64]


def occurrence_rows(
    tt: CompactTimetable,
    day: date,
    low: int,
    high: int,
    delays: Mapping[tuple[str, date], int],
) -> Rows:
    counts = np.diff(tt.trip_ptr).astype(np.int64)
    owner = np.repeat(np.arange(tt.trips), counts)
    parts: list[Rows] = []
    delayed = {
        (tt.trip_ids.index(trip) if trip in tt.trip_ids else -1, when): seconds
        for (trip, when), seconds in delays.items()
    }
    for shift in SHIFTS:
        actual = day + timedelta(days=shift)
        active = tt.active_services(actual)
        trip_ok = (tt.trip_service >= 0) & active[np.maximum(tt.trip_service, 0)]
        rows = trip_ok[owner]
        offset = np.full(tt.st_stop.size, shift * DAY, dtype=np.int64)
        for (trip, when), seconds in delayed.items():
            if when == actual and trip >= 0:
                offset[tt.trip_ptr[trip] : tt.trip_ptr[trip + 1]] += seconds
        arr = tt.st_arr.astype(np.int64) + offset
        dep = tt.st_dep.astype(np.int64) + offset
        # Keep a trip occurrence if any of its calls falls in the window.
        inside = rows & (dep >= low) & (arr <= high)
        keep_trip = np.zeros(tt.trips, dtype=bool)
        keep_trip[np.unique(owner[inside])] = True
        rows = rows & keep_trip[owner]
        index = np.flatnonzero(rows)
        parts.append(
            Rows(
                trip=owner[index],
                shift=np.full(index.size, shift, dtype=np.int64),
                stop=tt.st_stop[index],
                arr=arr[index],
                dep=dep[index],
                pickup=tt.st_pickup[index] == 1,
                dropoff=tt.st_dropoff[index] == 1,
                first=np.empty(0, dtype=np.intp),
                rank=np.empty(0, dtype=np.int64),
            )
        )
    joined = Rows(
        trip=np.concatenate([part.trip for part in parts]),
        shift=np.concatenate([part.shift for part in parts]),
        stop=np.concatenate([part.stop for part in parts]),
        arr=np.concatenate([part.arr for part in parts]),
        dep=np.concatenate([part.dep for part in parts]),
        pickup=np.concatenate([part.pickup for part in parts]),
        dropoff=np.concatenate([part.dropoff for part in parts]),
        first=np.empty(0, dtype=np.intp),
        rank=np.empty(0, dtype=np.int64),
    )
    key = joined.trip * 3 + (joined.shift + 1)
    start = np.r_[True, key[1:] != key[:-1]] if key.size else np.empty(0, dtype=bool)
    first = np.flatnonzero(start)
    rank = np.cumsum(start) - 1
    return Rows(
        joined.trip,
        joined.shift,
        joined.stop,
        joined.arr,
        joined.dep,
        joined.pickup,
        joined.dropoff,
        first,
        rank,
    )


def boarded_before(rows: Rows, boardable: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Whether an earlier call of the same occurrence was boardable."""
    cumulative = np.cumsum(boardable)
    prior = cumulative - boardable
    return (prior - prior[rows.first][rows.rank]) > 0


def alights_after(rows: Rows, alightable: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Whether a later call of the same occurrence is alightable."""
    reverse = np.cumsum(alightable[::-1])[::-1]
    after = reverse - alightable
    ends = np.r_[rows.first[1:], rows.stop.size] - 1
    return (
        (after - (reverse[ends] - alightable[ends])[rows.rank]) > 0 if rows.stop.size else after > 0
    )


def forward(
    rows: Rows, footpaths: Footpaths, size: int, origin: int, ready: int, rounds: int
) -> NDArray[np.int64]:
    reach = np.full(size, NEVER, dtype=np.int64)
    reach[origin] = ready
    origins = np.repeat(np.arange(size), np.diff(footpaths.pointer))
    for _ in range(rounds):
        boardable = rows.pickup & (reach[rows.stop] <= rows.dep)
        candidate = rows.dropoff & boarded_before(rows, boardable)
        updated = reach.copy()
        np.minimum.at(updated, rows.stop[candidate], rows.arr[candidate])
        np.minimum.at(updated, footpaths.destination, updated[origins] + footpaths.seconds)
        if np.array_equal(updated, reach):
            break
        reach = updated
    return reach


def backward(
    rows: Rows, footpaths: Footpaths, size: int, targets: list[int], deadline: int, rounds: int
) -> NDArray[np.int64]:
    latest = np.full(size, -NEVER, dtype=np.int64)
    latest[targets] = deadline
    origins = np.repeat(np.arange(size), np.diff(footpaths.pointer))
    for _ in range(rounds):
        alightable = rows.dropoff & (rows.arr <= latest[rows.stop])
        candidate = rows.pickup & alights_after(rows, alightable)
        updated = latest.copy()
        np.maximum.at(updated, rows.stop[candidate], rows.dep[candidate])
        np.maximum.at(updated, origins, updated[footpaths.destination] - footpaths.seconds)
        if np.array_equal(updated, latest):
            break
        latest = updated
    return latest


def relevant(
    rows: Rows, reach: NDArray[np.int64], latest: NDArray[np.int64], horizon: int
) -> NDArray[np.bool_]:
    """Rows of occurrences with a boardable call followed by a call that can still finish."""
    boardable = rows.pickup & (reach[rows.stop] <= rows.dep) & (rows.dep <= horizon)
    reached = boarded_before(rows, boardable)
    alightable = rows.dropoff & (rows.arr <= latest[rows.stop]) & reached
    keep = np.zeros(rows.first.size, dtype=bool)
    keep[np.unique(rows.rank[alightable])] = True
    return keep[rows.rank]


def window_schedule(
    tt: CompactTimetable,
    footpaths: Footpaths,
    scenario: Scenario,
    delays: Mapping[tuple[str, date], int] | None = None,
) -> Window:
    index = {name: position for position, name in enumerate(tt.stop_ids)}
    delays = delays or {}
    low = min(scenario.a.ready, scenario.b.ready)
    deadline = scenario.meeting_end
    high = min(
        deadline,
        max(scenario.a.ready + scenario.a.travel_limit, scenario.b.ready + scenario.b.travel_limit),
    )
    slack = 43200 if delays else 0
    rows = occurrence_rows(tt, scenario.service_date, low, high + slack, delays)
    size = len(tt.stop_ids)
    rounds = max(scenario.a.transfer_limit, scenario.b.transfer_limit) + 1
    targets = [index[name] for name in scenario.destinations]
    latest = backward(rows, footpaths, size, targets, deadline, rounds)
    keep = np.zeros(rows.stop.size, dtype=bool)
    bound = scenario.meeting_start
    for rider in (scenario.a, scenario.b):
        reach = forward(rows, footpaths, size, index[rider.stop], rider.ready, rounds)
        keep |= relevant(rows, reach, latest, rider.ready + rider.travel_limit)
        bound = max(bound, int(min(reach[target] for target in targets)))
    window = build_schedule(tt, footpaths, scenario, rows, keep, index)
    return Window(window.schedule, window.occurrences, window.rows, window.kept_trips, bound)


def build_schedule(
    tt: CompactTimetable,
    footpaths: Footpaths,
    scenario: Scenario,
    rows: Rows,
    keep: NDArray[np.bool_],
    index: dict[str, int],
) -> Window:
    trips_kept = np.unique(rows.trip[keep])
    stops_used = set(np.unique(rows.stop[keep]).tolist())
    stops_used.update(
        index[name] for name in (scenario.a.stop, scenario.b.stop, *scenario.destinations)
    )
    services: dict[str, Service] = {}
    exceptions: dict[tuple[str, date], bool] = {}
    trips: dict[str, Trip] = {}
    actives = {
        shift: tt.active_services(scenario.service_date + timedelta(days=shift)) for shift in SHIFTS
    }
    for position in trips_kept.tolist():
        service = int(tt.trip_service[position])
        name = tt.service_ids[service]
        if name not in services:
            services[name] = Service(date.min, date.max, (False,) * 7)
            for shift in SHIFTS:
                exceptions[name, scenario.service_date + timedelta(days=shift)] = bool(
                    actives[shift][service]
                )
        low, high = int(tt.trip_ptr[position]), int(tt.trip_ptr[position + 1])
        stops_used.update(tt.st_stop[low:high].tolist())
        trips[tt.trip_ids[position]] = Trip(
            id=tt.trip_ids[position],
            route=tt.trip_routes[position],
            service=name,
            calls=tuple(
                StopTime(
                    stop=tt.stop_ids[int(tt.st_stop[k])],
                    arrival=int(tt.st_arr[k]),
                    departure=int(tt.st_dep[k]),
                    pickup=bool(tt.st_pickup[k]),
                    dropoff=bool(tt.st_dropoff[k]),
                )
                for k in range(low, high)
            ),
        )
    stops = {
        tt.stop_ids[i]: Stop(
            id=tt.stop_ids[i],
            name=tt.stop_names[i],
            longitude=float(tt.stop_lon[i]),
            latitude=float(tt.stop_lat[i]),
        )
        for i in stops_used
    }
    used = np.zeros(len(tt.stop_ids), dtype=bool)
    used[list(stops_used)] = True
    origins = np.repeat(np.arange(len(tt.stop_ids)), np.diff(footpaths.pointer))
    both = used[origins] & used[footpaths.destination]
    transfers = tuple(
        Transfer(origin=tt.stop_ids[int(a)], destination=tt.stop_ids[int(b)], duration=int(d))
        for a, b, d in zip(
            origins[both], footpaths.destination[both], footpaths.seconds[both], strict=True
        )
    )
    schedule = Schedule(stops, trips, services, exceptions, transfers)
    return Window(
        schedule,
        int(np.unique(rows.trip * 3 + rows.shift + 1).size),
        int(rows.stop.size),
        len(trips),
    )


HORIZONS = (1800, 3600, 7200)


def route(
    tt: CompactTimetable,
    footpaths: Footpaths,
    scenario: Scenario,
    *,
    overlay: Overlay | None = None,
    limit: int = 6,
    budget: Budget | None = None,
    stats: SearchStats | None = None,
    horizons: tuple[int, ...] = HORIZONS,
) -> tuple[list[Offer], Window]:
    """Return the best offers. Meetings are searched in growing horizons past a lower bound.

    Offers rank by meeting time first, so when a horizon already yields `limit` offers, no later
    meeting can rank among them and the result equals the search over the whole window.
    """
    delays = overlay.delays if overlay else None
    budget = budget or Budget()
    full = window_schedule(tt, footpaths, scenario, delays)
    if full.lower_bound > scenario.meeting_end:
        return [], full
    for horizon in horizons:
        end = full.lower_bound + horizon
        if end >= scenario.meeting_end:
            break
        narrowed = scenario.model_copy(update={"meeting_end": end})
        window = window_schedule(tt, footpaths, narrowed, delays)
        offers = find_offers(
            window.schedule, narrowed, overlay=overlay, limit=limit, budget=budget, stats=stats
        )
        if len(offers) >= limit:
            return offers, window
    offers = find_offers(
        full.schedule, scenario, overlay=overlay, limit=limit, budget=budget, stats=stats
    )
    return offers, full
