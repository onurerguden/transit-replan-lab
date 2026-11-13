"""The bounded search on the compiled network must equal the search on the whole schedule."""

import json
import random
from datetime import date
from functools import cache
from pathlib import Path

import pytest

from trl.disruptions import Overlay
from trl.domain import Constraint, Scenario, StopClosure
from trl.gtfs import DATA_ROOT, Schedule, load_schedule
from trl.routing import Budget, SearchIncomplete, find_offers
from trl.scenarios import load_scenario
from trl.timetable.compact import CompactTimetable, compile_timetable, get_timetable
from trl.timetable.footpaths import Footpaths, from_transfers
from trl.timetable.query import route
from trl.verify import check_plan

ROOT = DATA_ROOT / "gtfs"
DAY = load_scenario().service_date


@cache
def core() -> tuple[CompactTimetable, Footpaths, Schedule]:
    table = compile_timetable(ROOT, "core")
    documented = {
        (item["origin"], item["destination"]): item["duration"]
        for item in json.loads((ROOT / "transfers.json").read_text())
    }
    return table, from_transfers(table.stop_ids, documented), load_schedule()


def scenario(rng: random.Random, stops: list[str]) -> Scenario:
    a, b, d = rng.sample(stops, 3)
    ready = rng.randrange(6 * 3600, 20 * 3600, 60)
    return Scenario(
        id="random",
        service_date=DAY,
        a=Constraint(stop=a, ready=ready, wait_limit=rng.choice([300, 600, 1200])),
        b=Constraint(stop=b, ready=ready + rng.randrange(0, 900, 60), wait_limit=600),
        destinations=(d,),
        meeting_start=ready,
        meeting_end=ready + 5400,
        notice="",
        incident=StopClosure(stop=a, start=0, end=1),
    )


def test_core_compilation_matches_the_object_schedule() -> None:
    table, _, schedule = core()
    assert table.trips == len(schedule.trips)
    assert set(table.trip_ids) == set(schedule.trips)
    assert set(table.stop_ids) >= set(schedule.stops)
    assert table.stop_times == sum(len(trip.calls) for trip in schedule.trips.values())


@pytest.mark.parametrize("seed", range(6))
def test_bounded_search_equals_full_search_on_the_core_network(seed: int) -> None:
    table, footpaths, schedule = core()
    rng = random.Random(seed)
    stops = sorted(schedule.stops)
    compared = feasible = 0
    for _ in range(8):
        query = scenario(rng, stops)
        overlay = Overlay.compile(
            (StopClosure(stop=rng.choice(stops), start=query.a.ready, end=query.a.ready + 1500),)
        )
        expected = find_offers(schedule, query, overlay=overlay)
        offers, window = route(table, footpaths, query, overlay=overlay)
        assert offers == expected
        assert window.kept_trips <= table.trips
        compared += 1
        feasible += bool(expected)
        for offer in offers:
            assert check_plan(window.schedule, query, offer, overlay) is None
    assert compared == 8 and feasible >= 0


def test_the_bound_keeps_far_fewer_trips_than_the_network() -> None:
    table, footpaths, schedule = core()
    query = scenario(random.Random(11), sorted(schedule.stops))
    _, window = route(table, footpaths, query)
    assert window.kept_trips < table.trips


def test_an_exhausted_budget_is_an_explicit_incomplete_outcome() -> None:
    table, footpaths, schedule = core()
    query = scenario(random.Random(2), sorted(schedule.stops))
    with pytest.raises(SearchIncomplete):
        route(table, footpaths, query, budget=Budget(max_work=3))


def test_the_compiled_cache_round_trips(tmp_path: Path) -> None:
    first = get_timetable(ROOT, tmp_path, "core")
    second = get_timetable(ROOT, tmp_path, "core")
    assert first.key == second.key and first.trip_ids == second.trip_ids
    assert (first.st_dep == second.st_dep).all()
    assert len(list(tmp_path.glob("*.npz"))) == 1


def test_delays_widen_the_bound_without_changing_the_answer() -> None:
    table, footpaths, schedule = core()
    query = scenario(random.Random(5), sorted(schedule.stops))
    trip = next(item for item in schedule.trips.values() if schedule.runs(item.service, DAY)).id
    overlay = Overlay.compile(())
    delayed = Overlay(overlay.closures, overlay.cancellations, {(trip, DAY): 600})
    expected = find_offers(schedule, query, overlay=delayed)
    offers, _ = route(table, footpaths, query, overlay=delayed)
    assert offers == expected
    assert date.min < DAY
