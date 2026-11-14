"""Compare the router and the independent verifier with an exhaustive journey oracle."""

from dataclasses import dataclass
from datetime import date

import pytest
from hypothesis import event, given, settings
from hypothesis import strategies as st

from trl.disruptions import Overlay
from trl.domain import (
    Constraint,
    Disruption,
    Scenario,
    Stop,
    StopClosure,
    StopTime,
    Trip,
    TripCancellation,
    TripDelay,
)
from trl.gtfs import Schedule, Service
from trl.routing import find_offers
from trl.verifier import verify_offer
from trl.verifier.semantics import IncidentState

DAY = date(2026, 10, 21)
STOPS = "abcd"
RIDES = 3


@dataclass(frozen=True)
class Call:
    stop: str
    at: int
    pickup: bool
    dropoff: bool


Plan = list[list[Call]]


def build(plan: Plan) -> Schedule:
    trips = {
        str(index): Trip(
            id=str(index),
            route="R",
            service="daily",
            calls=tuple(
                StopTime(
                    stop=c.stop, arrival=c.at, departure=c.at, pickup=c.pickup, dropoff=c.dropoff
                )
                for c in calls
            ),
        )
        for index, calls in enumerate(plan)
    }
    return Schedule(
        {name: Stop(id=name, name=name, longitude=27, latitude=38) for name in STOPS},
        trips,
        {"daily": Service(date(2026, 10, 20), DAY, (True,) * 7)},
        {},
        (),
    )


def closed_at(closures: list[tuple[str, int, int]], stop: str, second: int) -> bool:
    return any(s == stop and a <= second < b for s, a, b in closures)


def present(closures: list[tuple[str, int, int]], stop: str, first: int, last: int) -> bool:
    return any(closed_at(closures, stop, second) for second in range(first, last + 1))


def arrivals(
    plan: Plan,
    closures: list[tuple[str, int, int]],
    cancelled: int | None,
    delay: tuple[int, int] | None,
    origin: str,
) -> list[tuple[int, int]]:
    """Every (arrival at d, rides) reachable without being present at a closed stop."""
    found: list[tuple[int, int]] = []

    def walk(stop: str, at: int, rides: int) -> None:
        if stop == "d":
            found.append((at, rides))
            return
        if rides == RIDES:
            return
        for index, calls in enumerate(plan):
            if index == cancelled:
                continue
            shift = delay[1] if delay and delay[0] == index else 0
            for i, board in enumerate(calls[:-1]):
                departure = board.at + shift
                if board.stop != stop or not board.pickup or departure < at:
                    continue
                if present(closures, stop, at, departure):
                    continue
                for alight in calls[i + 1 :]:
                    if alight.dropoff:
                        walk(alight.stop, alight.at + shift, rides + 1)

    walk(origin, 0, 0)
    return found


@st.composite
def trips(draw: st.DrawFn) -> Plan:
    """Build trips that usually start at a rider origin and often end at the destination."""
    plan: Plan = []
    for _ in range(draw(st.integers(2, 7))):
        middle = draw(st.lists(st.sampled_from("abc"), min_size=1, max_size=3, unique=True))
        stops = [*middle, "d"] if draw(st.integers(0, 9)) < 7 else middle
        at = draw(st.integers(0, 12))
        calls: list[Call] = []
        for stop in stops:
            at += draw(st.integers(1, 5))
            calls.append(
                Call(
                    stop,
                    at,
                    draw(st.integers(0, 9)) > 0,
                    draw(st.integers(0, 9)) > 0,
                )
            )
        if len(calls) >= 2:
            plan.append(calls)
    return plan


@given(
    trips(),
    st.integers(0, 10),
    st.integers(0, 10),
    st.one_of(st.none(), st.tuples(st.sampled_from(STOPS), st.integers(0, 28), st.integers(1, 8))),
    st.one_of(st.none(), st.integers(0, 5)),
    st.one_of(st.none(), st.tuples(st.integers(0, 5), st.integers(1, 4))),
)
@settings(max_examples=300, deadline=None)
def test_router_and_verifier_agree_with_the_exhaustive_oracle(
    plan: Plan,
    wait_a: int,
    wait_b: int,
    closure: tuple[str, int, int] | None,
    cancelled: int | None,
    delay: tuple[int, int] | None,
) -> None:
    if not plan:
        return
    closures = [(closure[0], closure[1], closure[1] + closure[2])] if closure else []
    schedule = build(plan)
    scenario = Scenario(
        id="oracle",
        service_date=DAY,
        a=Constraint(stop="a", ready=0, wait_limit=wait_a, transfer_limit=RIDES - 1),
        b=Constraint(stop="b", ready=0, wait_limit=wait_b, transfer_limit=RIDES - 1),
        destinations=("d",),
        meeting_start=0,
        meeting_end=60,
        notice="",
        incident=StopClosure(stop="a", start=100, end=101),
    )
    incidents: list[Disruption] = [StopClosure(stop=s, start=a, end=b) for s, a, b in closures]
    incidents += (
        [TripCancellation(trip=str(cancelled), service_date=DAY)] if cancelled is not None else []
    )
    if delay is not None:
        incidents.append(TripDelay(trip=str(delay[0]), service_date=DAY, seconds=delay[1]))
    overlay = Overlay.compile(incidents)
    state = IncidentState.from_disruptions(incidents)

    arrive_a = arrivals(plan, closures, cancelled, delay, "a")
    arrive_b = arrivals(plan, closures, cancelled, delay, "b")
    expected = min(
        (
            (max(a, b), max(0, ra - 1) + max(0, rb - 1))
            for a, ra in arrive_a
            for b, rb in arrive_b
            if max(a, b) <= min(a + wait_a, b + wait_b, 60)
            and not present(closures, "d", min(a, b), max(a, b))
        ),
        default=None,
    )
    event(f"feasible={expected is not None}")
    offers = find_offers(schedule, scenario, limit=1, overlay=overlay)
    assert bool(offers) == (expected is not None)
    for offer in offers:
        assert (
            offer.meeting,
            max(0, len(offer.a.legs) - 1) + max(0, len(offer.b.legs) - 1),
        ) == expected
        from trl.domain import Vote

        votes = tuple(
            Vote(rider=rider, version=0, offer_id=offer.id, accepted=True) for rider in ("a", "b")
        )
        assert verify_offer(schedule, scenario, offer, votes, 0, state) is None


@pytest.mark.parametrize("shift", [-1, 1])
def test_verifier_rejects_a_departure_off_by_one_second(shift: int) -> None:
    plan = [
        [Call("a", 2, True, True), Call("d", 5, True, True)],
        [Call("b", 1, True, True), Call("d", 4, True, True)],
    ]
    schedule = build(plan)
    scenario = Scenario(
        id="mutation",
        service_date=DAY,
        a=Constraint(stop="a", ready=0, wait_limit=5),
        b=Constraint(stop="b", ready=0, wait_limit=5),
        destinations=("d",),
        meeting_start=0,
        meeting_end=60,
        notice="",
        incident=StopClosure(stop="a", start=100, end=101),
    )
    offer = find_offers(schedule, scenario, limit=1)[0]
    ride = offer.a.legs[0]
    moved = ride.model_copy(update={"departure": ride.departure + shift})
    forged = offer.model_copy(
        update={"a": offer.a.model_copy(update={"legs": (moved, *offer.a.legs[1:])})}
    )
    from trl.verifier import check_plan

    assert check_plan(schedule, scenario, forged, IncidentState()) is not None


@given(trips(), st.integers(0, 10), st.integers(0, 10))
@settings(max_examples=100, deadline=None)
def test_frozen_label_search_matches_the_router_today(plan: Plan, wait_a: int, wait_b: int) -> None:
    """The frozen oracle and the live router start identical, so routing v2 has a fixed target."""
    import label_search_oracle

    if not plan:
        return
    schedule = build(plan)
    scenario = Scenario(
        id="frozen",
        service_date=DAY,
        a=Constraint(stop="a", ready=0, wait_limit=wait_a, transfer_limit=RIDES - 1),
        b=Constraint(stop="b", ready=0, wait_limit=wait_b, transfer_limit=RIDES - 1),
        destinations=("d",),
        meeting_start=0,
        meeting_end=60,
        notice="",
        incident=StopClosure(stop="a", start=100, end=101),
    )
    assert label_search_oracle.find_offers(schedule, scenario) == find_offers(schedule, scenario)
