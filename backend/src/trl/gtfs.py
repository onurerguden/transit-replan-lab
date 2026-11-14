"""Read the two frozen GTFS feeds without extracting archive members."""

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from zipfile import ZipFile

from pydantic import TypeAdapter

from trl.domain import Record, Stop, StopTime, Transfer, Trip
from trl.settings import get_settings

DATA_ROOT: Path = get_settings().data


Mode = Literal["metro", "tram", "rail", "bus", "ferry"]
CalendarPolicy = Literal["strict", "project_weekdays"]
Profile = Literal["core", "full"]


class Feed(Record):
    """One official archive. `routes` selects routes for the core profile."""

    id: str
    url: str
    # An archive that is unavailable upstream has no checksum or calendar bounds.
    sha256: str | None = None
    routes: tuple[str, ...] = ()
    start: date | None = None
    end: date | None = None
    mode: Mode = "rail"
    optional: bool = False
    # `project_weekdays` repeats the weekly pattern outside the published calendar. It is an
    # assumption, recorded in the feed health report and shown with the plan.
    calendar_policy: CalendarPolicy = "strict"
    profiles: tuple[Profile, ...] = ("core", "full")


@dataclass(frozen=True)
class Service:
    start: date
    end: date
    weekdays: tuple[bool, ...]


@dataclass(frozen=True)
class Schedule:
    stops: dict[str, Stop]
    trips: dict[str, Trip]
    services: dict[str, Service]
    exceptions: dict[tuple[str, date], bool]
    transfers: tuple[Transfer, ...]

    def runs(self, service_id: str, day: date) -> bool:
        exception = self.exceptions.get((service_id, day))
        if exception is not None:
            return exception
        service = self.services.get(service_id)
        return service is not None and (
            service.start <= day <= service.end and service.weekdays[day.weekday()]
        )


def feed_specs(root: Path) -> list[Feed]:
    return TypeAdapter(list[Feed]).validate_json((root / "feeds.json").read_bytes())


def checked_archive(path: Path, sha256: str | None) -> bytes:
    data = path.read_bytes()
    if sha256 is None or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError(f"SHA-256 mismatch: {path.name}")
    return data


def service_second(value: str) -> int:
    hour, minute, second = (int(part) for part in value.split(":"))
    if hour < 0 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError(f"Invalid GTFS service time: {value}")
    return hour * 3600 + minute * 60 + second


def service_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def rows(archive: ZipFile, name: str, *, optional: bool = False) -> list[dict[str, str]]:
    if optional and name not in archive.namelist():
        return []
    with io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def accessibility(value: str | None) -> bool | None:
    return {"1": True, "2": False}.get(value or "")


def read_feed(data: bytes, feed: Feed) -> Schedule:
    def scoped(value: str) -> str:
        return f"{feed.id}:{value}"

    with ZipFile(io.BytesIO(data)) as archive:
        trip_rows = {
            row["trip_id"]: row
            for row in rows(archive, "trips.txt")
            if row["route_id"] in feed.routes
        }
        calls: dict[str, list[tuple[int, StopTime]]] = {key: [] for key in trip_rows}
        stop_ids: set[str] = set()
        for row in rows(archive, "stop_times.txt"):
            if row["trip_id"] not in calls:
                continue
            stop = row["stop_id"]
            stop_ids.add(stop)
            calls[row["trip_id"]].append(
                (
                    int(row["stop_sequence"]),
                    StopTime(
                        stop=scoped(stop),
                        arrival=service_second(row["arrival_time"]),
                        departure=service_second(row["departure_time"]),
                        pickup=(row.get("pickup_type") or "0") == "0",
                        dropoff=(row.get("drop_off_type") or "0") == "0",
                    ),
                )
            )
        stops = {
            scoped(row["stop_id"]): Stop(
                id=scoped(row["stop_id"]),
                name=row["stop_name"],
                longitude=float(row["stop_lon"]),
                latitude=float(row["stop_lat"]),
                accessible=accessibility(row.get("wheelchair_boarding")),
            )
            for row in rows(archive, "stops.txt")
            if row["stop_id"] in stop_ids
        }
        services = {
            scoped(row["service_id"]): Service(
                service_date(row["start_date"]),
                service_date(row["end_date"]),
                tuple(
                    row[weekday] == "1"
                    for weekday in (
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    )
                ),
            )
            for row in rows(archive, "calendar.txt", optional=True)
        }
        exceptions = {
            (scoped(row["service_id"]), service_date(row["date"])): row["exception_type"] == "1"
            for row in rows(archive, "calendar_dates.txt", optional=True)
        }

    trips = {
        scoped(key): Trip(
            id=scoped(key),
            route=scoped(row["route_id"]),
            service=scoped(row["service_id"]),
            calls=tuple(call for _, call in sorted(calls[key], key=lambda pair: pair[0])),
            accessible=accessibility(row.get("wheelchair_accessible")),
        )
        for key, row in trip_rows.items()
    }
    for trip in trips.values():
        last = -1
        for call in trip.calls:
            if call.stop not in stops or not last <= call.arrival <= call.departure:
                raise ValueError(f"Invalid call sequence on {trip.id}.")
            last = call.departure
        if len(trip.calls) < 2:
            raise ValueError(f"Trip {trip.id} has fewer than two scheduled calls.")
    return Schedule(stops, trips, services, exceptions, ())


def load_schedule(root: Path = DATA_ROOT / "gtfs") -> Schedule:
    # The routing core loads the pinned core profile. The full network is compiled separately.
    feeds = [
        read_feed(checked_archive(root / f"{feed.id}.zip", feed.sha256), feed)
        for feed in feed_specs(root)
        if "core" in feed.profiles
    ]
    transfers = TypeAdapter(tuple[Transfer, ...]).validate_json(
        (root / "transfers.json").read_bytes()
    )
    stops = {key: stop for feed in feeds for key, stop in feed.stops.items()}
    for link in transfers:
        if link.origin not in stops or link.destination not in stops:
            raise ValueError("Transfer endpoint is absent from the selected routes.")
    return Schedule(
        stops,
        {key: trip for feed in feeds for key, trip in feed.trips.items()},
        {key: service for feed in feeds for key, service in feed.services.items()},
        {key: value for feed in feeds for key, value in feed.exceptions.items()},
        transfers,
    )
