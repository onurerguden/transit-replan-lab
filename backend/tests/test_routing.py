from dataclasses import replace
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from trl import routing
from trl.disruptions import Overlay
from trl.domain import (
    Constraint,
    Itinerary,
    Offer,
    Scenario,
    Stop,
    StopClosure,
    StopTime,
    Transfer,
    Trip,
    TripCancellation,
    TripDelay,
    Vote,
)
from trl.gtfs import Schedule, Service, load_schedule
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.verify import verify_offer

DAY = date(2026, 10, 21)
EMPTY = Overlay.compile(())
Edge = tuple[str, str, int, int]


def network(edges: list[Edge]) -> Schedule:
    return Schedule(
        {name: Stop(id=name, name=name, longitude=27, latitude=38) for name in "abcd"},
        {
            str(i): Trip(
                id=str(i),
                route="R",
                service="daily",
                calls=(
                    StopTime(stop=a, arrival=depart, departure=depart),
                    StopTime(stop=b, arrival=arrive, departure=arrive),
                ),
            )
            for i, (a, b, depart, arrive) in enumerate(edges)
        },
        {"daily": Service(date(2026, 10, 20), DAY, (True,) * 7)},
        {},
        (),
    )


def small(wait_a: int = 6, wait_b: int = 6) -> Scenario:
    return Scenario(
        id="small",
        service_date=DAY,
        a=Constraint(stop="a", ready=0, wait_limit=wait_a, transfer_limit=2),
        b=Constraint(stop="b", ready=0, wait_limit=wait_b, transfer_limit=2),
        destinations=("d",),
        meeting_start=0,
        meeting_end=30,
        notice="",
        incident=StopClosure(stop="d", start=10, end=20),
    )


def votes(offer: Offer) -> tuple[Vote, Vote]:
    return (
        Vote(rider="a", version=offer.version, offer_id=offer.id, accepted=True),
        Vote(rider="b", version=offer.version, offer_id=offer.id, accepted=True),
    )


def exhaustive(edges: list[Edge], origin: str, at: int, remaining: int) -> list[tuple[int, int]]:
    arrivals = [(at, 0)] if origin == "d" else []
    if remaining:
        for left, right, departure, arrival in edges:
            if left == origin and at <= departure:
                arrivals.extend(
                    (time, rides + 1)
                    for time, rides in exhaustive(edges, right, arrival, remaining - 1)
                )
    return arrivals


@given(
    st.lists(
        st.tuples(
            st.sampled_from(list("abc")),
            st.sampled_from(list("abcd")),
            st.integers(0, 24),
            st.integers(1, 5),
        ),
        max_size=12,
    ),
    st.integers(0, 12),
    st.integers(0, 12),
)
@settings(max_examples=100, deadline=None)
def test_optimum_matches_exhaustive_search(
    generated: list[Edge],
    wait_a: int,
    wait_b: int,
) -> None:
    edges = [(a, b, t, t + duration) for a, b, t, duration in generated if a != b]
    schedule = network(edges)
    scenario = small(wait_a, wait_b)
    expected = min(
        (
            (max(a, b), max(0, ar - 1) + max(0, br - 1))
            for a, ar in exhaustive(edges, "a", 0, 3)
            for b, br in exhaustive(edges, "b", 0, 3)
            if max(a, b) <= min(a + wait_a, b + wait_b, 30)
        ),
        default=None,
    )
    offers = find_offers(schedule, scenario, limit=1)
    assert bool(offers) == (expected is not None)
    if offers:
        offer = offers[0]
        assert expected == (
            offer.meeting,
            max(0, len(offer.a.legs) - 1) + max(0, len(offer.b.legs) - 1),
        )
        assert verify_offer(schedule, scenario, offer, votes(offer), 0, EMPTY) is None


def test_later_departure_enables_joint_arrival() -> None:
    schedule = network([("a", "d", 2, 6), ("a", "d", 10, 15), ("b", "d", 11, 16)])
    scenario = small(2, 2)
    offer = find_offers(schedule, scenario)[0]
    assert offer.a.arrival == 15 and offer.meeting == 16
    assert not find_offers(schedule, scenario, overlay=Overlay.compile((scenario.incident,)))


def test_previous_service_day_trip_survives_midnight() -> None:
    schedule = network([("a", "d", 86404, 86410), ("b", "d", 86405, 86411)])
    scenario = small()
    offer = find_offers(schedule, scenario)[0]
    first = offer.a.legs[0]
    assert first.kind == "ride" and first.service_date == date(2026, 10, 20)
    assert offer.meeting == 11


def test_delayed_and_cancelled_trips() -> None:
    schedule = network([("a", "d", 3, 6), ("b", "d", 4, 8)])
    scenario = small()
    shifted = Overlay.compile((TripDelay(trip="0", service_date=DAY, seconds=4),))
    offer = find_offers(schedule, scenario, 1, shifted)[0]
    assert offer.a.arrival == 10
    assert verify_offer(schedule, scenario, offer, votes(offer), 1, shifted) is None
    cancelled = Overlay.compile((TripCancellation(trip="0", service_date=DAY),))
    assert not find_offers(schedule, scenario, 1, cancelled)
    assert verify_offer(schedule, scenario, offer, votes(offer), 1, cancelled) == "inactive_trip"


def test_demo_changes_interchange_and_rejects_forged_evidence() -> None:
    schedule = load_schedule()
    scenario = load_scenario()
    initial = find_offers(schedule, scenario, limit=1)[0]
    overlay = Overlay.compile((scenario.incident,))
    offer = find_offers(schedule, scenario, 1, overlay)[0]
    assert initial.a.legs[1].destination == "tram:7"
    assert offer.a.legs[1].destination == "tram:21"
    assert offer.meeting > initial.meeting
    assert verify_offer(schedule, scenario, offer, votes(offer), 1, overlay) is None
    assert (
        verify_offer(schedule, scenario, initial, votes(initial), 0, overlay) == "closed_transfer"
    )
    assert verify_offer(schedule, scenario, offer, votes(initial), 1, overlay)
    assert verify_offer(schedule, scenario, offer, (votes(offer)[0],) * 2, 1, overlay)
    for field, value in (("arrival", 0), ("destination", "tram:7"), ("start", 0)):
        forged = offer.model_copy(update={"a": offer.a.model_copy(update={field: value})})
        assert verify_offer(schedule, scenario, forged, votes(offer), 1, overlay)
    leg = offer.a.legs[0].model_copy(update={"departure": offer.a.legs[0].departure + 1})
    route = offer.a.model_copy(update={"legs": (leg, *offer.a.legs[1:])})
    assert (
        verify_offer(
            schedule, scenario, offer.model_copy(update={"a": route}), votes(offer), 1, overlay
        )
        == "timetable_mismatch"
    )
    constrained = scenario.model_copy(
        update={"a": scenario.a.model_copy(update={"accessible_only": True})}
    )
    assert not find_offers(schedule, constrained, 1, overlay)
    assert (
        verify_offer(schedule, constrained, offer, votes(offer), 1, overlay)
        == "unknown_stop_accessibility"
    )


def test_verifier_rejects_broken_legs_limits_and_meeting() -> None:
    schedule = load_schedule()
    scenario = load_scenario()
    offer = find_offers(schedule, scenario, limit=1)[0]
    walk = offer.a.legs[1]
    ride = offer.a.legs[0]

    def edit_leg(index: int, **changes: object) -> Offer:
        legs = list(offer.a.legs)
        legs[index] = legs[index].model_copy(update=changes)
        return offer.model_copy(update={"a": offer.a.model_copy(update={"legs": tuple(legs)})})

    assert (
        verify_offer(schedule, scenario, edit_leg(0, origin="missing"), votes(offer), 0, EMPTY)
        == "discontinuous_legs"
    )
    assert (
        verify_offer(schedule, scenario, edit_leg(0, board_index=999), votes(offer), 0, EMPTY)
        == "invalid_call_indices"
    )
    assert (
        verify_offer(
            schedule, scenario, edit_leg(1, arrival=walk.arrival - 1), votes(offer), 0, EMPTY
        )
        == "invalid_transfer"
    )
    closed = Overlay.compile(
        (StopClosure(stop=ride.origin, start=ride.departure, end=ride.departure + 1),)
    )
    assert verify_offer(schedule, scenario, offer, votes(offer), 0, closed) == "closed_platform"
    restricted = scenario.model_copy(
        update={
            "a": scenario.a.model_copy(update={"walk_limit": 0}),
        }
    )
    assert verify_offer(schedule, restricted, offer, votes(offer), 0, EMPTY) == "rider_limit"
    early = offer.model_copy(update={"meeting": 0})
    assert (
        verify_offer(schedule, scenario, early, votes(offer), 0, EMPTY) == "invalid_joint_arrival"
    )
    closed_destination = Overlay.compile(
        (StopClosure(stop=offer.a.destination, start=offer.b.arrival + 1, end=offer.meeting + 1),)
    )
    assert (
        verify_offer(schedule, scenario, offer, votes(offer), 0, closed_destination)
        == "closed_platform"
    )


def test_waiting_upstream_enables_terminal_walk() -> None:
    schedule = replace(
        network([("b", "d", 12, 16)]),
        transfers=(Transfer(origin="a", destination="d", duration=4),),
    )
    scenario = small(2, 0)
    offer = find_offers(schedule, scenario)[0]
    assert (offer.a.arrival, offer.b.arrival, offer.meeting) == (14, 16, 16)
    assert verify_offer(schedule, scenario, offer, votes(offer), 0, EMPTY) is None


def test_verifier_requires_known_endpoints_for_zero_leg_itineraries() -> None:
    scenario = small().model_copy(
        update={
            "a": Constraint(stop="missing", ready=0, wait_limit=0),
            "b": Constraint(stop="missing", ready=0, wait_limit=0),
            "destinations": ("missing",),
        }
    )
    route = Itinerary(origin="missing", destination="missing", start=0, arrival=0, legs=())
    offer = Offer(id="v0-1", version=0, a=route, b=route, meeting=0)
    assert verify_offer(network([]), scenario, offer, votes(offer), 0, EMPTY) == "unknown_origin"


@given(
    st.integers(0, 25),
    st.integers(0, 25),
    st.integers(0, 6),
    st.integers(0, 6),
    st.integers(0, 25),
    st.integers(1, 5),
    st.sampled_from(["a", "d"]),
    st.booleans(),
)
@settings(max_examples=150, deadline=None)
def test_walking_windows_match_exhaustive_second_by_second_search(
    start_a: int,
    start_b: int,
    wait_a: int,
    wait_b: int,
    closed_at: int,
    closed_for: int,
    closed_stop: str,
    walk_b: bool,
) -> None:
    walks = (Transfer(origin="a", destination="d", duration=3),)
    if walk_b:
        walks += (Transfer(origin="b", destination="d", duration=2),)
    schedule = replace(network([("b", "d", start_b, start_b + 2)]), transfers=walks)
    scenario = small(wait_a, wait_b).model_copy(
        update={
            "a": Constraint(stop="a", ready=start_a, wait_limit=wait_a),
            "b": Constraint(stop="b", ready=start_b, wait_limit=wait_b),
        }
    )
    end = closed_at + closed_for
    overlay = Overlay.compile((StopClosure(stop=closed_stop, start=closed_at, end=end),))

    def open_between(stop: str, start: int, last: int) -> bool:
        return stop != closed_stop or not any(closed_at <= t < end for t in range(start, last + 1))

    def walk_arrivals(origin: str, ready: int, duration: int) -> list[int]:
        return [
            t + duration
            for t in range(ready, 31 - duration)
            if open_between(origin, t, t + duration) and open_between("d", t, t + duration)
        ]

    b_arrivals = walk_arrivals("b", start_b, 2) if walk_b else []
    if open_between("d", start_b + 2, start_b + 2):
        b_arrivals.append(start_b + 2)
    expected = min(
        (
            (meeting, max(a - start_a, b - start_b))
            for a in walk_arrivals("a", start_a, 3)
            for b in b_arrivals
            for meeting in range(max(a, b), min(a + wait_a, b + wait_b, 30) + 1)
            if open_between("d", min(a, b), meeting)
        ),
        default=None,
    )
    offers = find_offers(schedule, scenario, overlay=overlay)
    assert bool(offers) == (expected is not None)
    if offers:
        first = offers[0]
        assert (
            first.meeting,
            max(first.a.arrival - start_a, first.b.arrival - start_b),
        ) == expected
    for offer in offers:
        assert verify_offer(schedule, scenario, offer, votes(offer), 0, overlay) is None


def test_meeting_cannot_wait_through_a_destination_closure() -> None:
    schedule = network([("a", "d", 1, 7), ("b", "d", 2, 8)])
    scenario = small().model_copy(update={"meeting_start": 12})
    offer = find_offers(schedule, scenario)[0]
    overlay = Overlay.compile((StopClosure(stop="d", start=10, end=11),))
    assert not find_offers(schedule, scenario, overlay=overlay)
    assert verify_offer(schedule, scenario, offer, votes(offer), 0, overlay) == "closed_destination"


def test_unconfirmed_transfer_cannot_support_accessible_route() -> None:
    schedule = network([("b", "d", 12, 16)])
    schedule = replace(
        schedule,
        stops={
            key: stop.model_copy(update={"accessible": True})
            for key, stop in schedule.stops.items()
        },
        transfers=(Transfer(origin="a", destination="d", duration=4),),
    )
    scenario = small(2, 0)
    offer = find_offers(schedule, scenario)[0]
    strict = scenario.model_copy(
        update={"a": scenario.a.model_copy(update={"accessible_only": True})}
    )
    assert not find_offers(schedule, strict)
    assert (
        verify_offer(schedule, strict, offer, votes(offer), 0, EMPTY)
        == "unknown_transfer_accessibility"
    )


def test_pair_budget_exhaustion_is_a_search_error(monkeypatch: pytest.MonkeyPatch) -> None:
    schedule = network([("a", "d", 2, 7), ("b", "d", 3, 8)])
    monkeypatch.setattr(routing, "MAX_PAIRS", 0)
    with pytest.raises(routing.SearchIncomplete, match="pair budget"):
        find_offers(schedule, small())
