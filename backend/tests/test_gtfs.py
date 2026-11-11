import io
from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

from trl.gtfs import Feed, checked_archive, load_schedule, read_feed

DEMO_DATE = date(2026, 10, 21)


def test_pinned_feeds() -> None:
    schedule = load_schedule()
    assert schedule.stops["tram:3"].name == "Alsancak Gar"
    assert schedule.stops["tram:7"].accessible is None
    assert {trip.route for trip in schedule.trips.values()} == {"metro:1", "metro:2", "tram:KONAK"}
    assert len(schedule.transfers) == 4
    assert schedule.runs("metro:WEEKDAY", DEMO_DATE)
    assert schedule.runs("tram:WEEKDAY", DEMO_DATE)


def test_checksum_rejects_unexpected_data(tmp_path: Path) -> None:
    path = tmp_path / "feed.zip"
    path.write_bytes(b"Unexpected archive")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        checked_archive(path, "0" * 64)


def test_service_exception_and_stop_permissions() -> None:
    data = io.BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("trips.txt", "route_id,service_id,trip_id\nR,W,T\n")
        archive.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon\nA,Alpha,38,27\nB,Beta,38,27\n",
        )
        archive.writestr(
            "stop_times.txt",
            "trip_id,stop_id,stop_sequence,arrival_time,departure_time,pickup_type,drop_off_type\n"
            "T,A,1,24:10:00,24:10:00,1,0\nT,B,2,24:15:00,24:15:00,0,2\n",
        )
        archive.writestr(
            "calendar.txt",
            "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
            "W,1,1,1,1,1,0,0,20261001,20261031\n",
        )
        archive.writestr(
            "calendar_dates.txt", "service_id,date,exception_type\nW,20261021,2\nW,20261024,1\n"
        )
    schedule = read_feed(
        data.getvalue(),
        Feed(id="test", url="", sha256="", routes=("R",), start=DEMO_DATE, end=DEMO_DATE),
    )
    first, last = schedule.trips["test:T"].calls
    assert first.departure == 24 * 3600 + 600
    assert not first.pickup and not last.dropoff
    assert not schedule.runs("test:W", DEMO_DATE)
    assert schedule.runs("test:W", date(2026, 10, 24))
