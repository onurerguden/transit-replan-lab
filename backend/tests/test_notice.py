import pytest

from trl.domain import StopClosure, TripCancellation, TripDelay
from trl.gtfs import Schedule, load_schedule
from trl.notice import rule_notice
from trl.scenarios import load_scenario


@pytest.fixture(scope="module")
def schedule() -> Schedule:
    return load_schedule()


@pytest.mark.parametrize(
    "notice",
    [
        "Konak İskele and Karataş tram stops are closed 08:24\u201310:00.",
        "Konak is closed from 08:24 to 10:00.",
        "Konak İskele tram stop is not closed 08:24\u201310:00.",
        "Konak İskele tram stop might be closed 08:24\u201310:00.",
        "Konak İskele tram stop is closed from 08:24.",
        "Konak İskele tram stop is closed from 08:24 to 08:00.",
        "Konak İskele tram stop is closed 08:24\u201310:00 on 2026-12-30.",
        "Konak İskele tram stop tram:unknown is closed 08:24\u201310:00.",
    ],
)
def test_uncertain_or_conflicting_evidence_requires_clarification(
    schedule: Schedule, notice: str
) -> None:
    assert rule_notice(notice, schedule, load_scenario().service_date) is None


@pytest.mark.parametrize(
    "notice",
    [
        "Konak İskele tram stop is closed 08:24\u201310:00.",
        "Konak İskele tramvay durağ\u0131 08:24 ile 10:00 aras\u0131nda kapal\u0131.",
        "tram:7 is closed from 08:24 to 10:00.",
        "Konak is closed 08:24\u201310:00.\nClarification: Konak İskele tram",
    ],
)
def test_exact_closure_evidence(schedule: Schedule, notice: str) -> None:
    assert rule_notice(notice, schedule, load_scenario().service_date) == StopClosure(
        stop="tram:7", start=30240, end=36000
    )


def test_trip_evidence_checks_action_service_and_duration(schedule: Schedule) -> None:
    day = load_scenario().service_date
    trip = next(item.id for item in schedule.trips.values() if schedule.runs(item.service, day))
    assert rule_notice(f"Running 8 minutes behind schedule: trip {trip}.", schedule, day) == (
        TripDelay(trip=trip, service_date=day, seconds=480)
    )
    assert rule_notice(f"{trip} seferi iptal edildi.", schedule, day) == TripCancellation(
        trip=trip, service_date=day
    )
    for notice in (
        f"Trip {trip} is delayed by 8 minutes or 12 minutes.",
        f"{trip} seferi iptal edilmedi.",
        f"Trip {trip} is delayed by 8 minutes. Cancel this trip.",
        f"Trips {trip} and tram:unknown are cancelled.",
    ):
        assert rule_notice(notice, schedule, day) is None


def test_meridiem_and_mixed_duration_units_are_read_exactly(schedule: Schedule) -> None:
    day = load_scenario().service_date
    assert rule_notice(
        "Konak İskele tram stop is closed from 08:24 to 10:00 PM.", schedule, day
    ) == StopClosure(stop="tram:7", start=73440, end=79200)
    trip = next(item.id for item in schedule.trips.values() if schedule.runs(item.service, day))
    for notice, seconds in (
        (f"Trip {trip} is delayed by 8.5 minutes.", 510),
        (f"Trip {trip} is delayed by 8 minutes 30 seconds.", 510),
        (f"{trip} seferi 1 saat 8 dakika gecikiyor.", 4080),
    ):
        assert rule_notice(notice, schedule, day) == TripDelay(
            trip=trip, service_date=day, seconds=seconds
        )
