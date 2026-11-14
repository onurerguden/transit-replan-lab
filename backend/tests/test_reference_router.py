"""A second, independent router must agree with the label search when limits are loose."""

import random

import pytest
from experiments.bench_v3.reference_router import earliest_meeting
from test_compact_routing import core

from trl.domain import Constraint
from trl.routing import find_offers


def loose(stop: str, ready: int) -> Constraint:
    return Constraint(
        stop=stop,
        ready=ready,
        wait_limit=14400,
        travel_limit=14400,
        walk_limit=3600,
        transfer_limit=5,
    )


@pytest.mark.deep
def test_the_label_search_never_beats_the_reference_and_usually_matches_it() -> None:
    _, _, schedule = core()
    rng = random.Random(9)
    stops = sorted(schedule.stops)
    matched = compared = 0
    for _ in range(40):
        a, b, d = rng.sample(stops, 3)
        ready = rng.randrange(6 * 3600, 20 * 3600, 60)
        from trl.domain import Scenario, StopClosure
        from trl.scenarios import load_scenario

        query = Scenario(
            id="reference",
            service_date=load_scenario().service_date,
            a=loose(a, ready),
            b=loose(b, ready + rng.randrange(0, 900, 60)),
            destinations=(d,),
            meeting_start=ready,
            meeting_end=ready + 14400,
            notice="",
            incident=StopClosure(stop=a, start=0, end=1),
        )
        reference = earliest_meeting(schedule, query)
        offers = find_offers(schedule, query, limit=1)
        label = offers[0].meeting if offers else None
        if reference is None:
            assert label is None
            continue
        compared += 1
        assert label is None or label >= reference
        matched += label == reference
    assert compared >= 20 and matched / compared >= 0.95
