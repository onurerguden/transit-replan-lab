"""Check each official archive before routing trusts it.

The report separates an archive that is healthy from one that is missing, not an archive, or
whose calendar does not cover the simulated service day. A projected calendar is an
assumption and is labelled as one.
"""

import csv
import hashlib
import io
from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Literal
from zipfile import BadZipFile, ZipFile

from trl.domain import Record
from trl.gtfs import Feed, feed_specs, service_date, service_second

Status = Literal["ok", "projected_calendar", "stale_calendar", "unavailable"]
REQUIRED = ("stops.txt", "trips.txt", "stop_times.txt", "routes.txt")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SAMPLE_LIMIT = 5


class FeedHealth(Record):
    id: str
    mode: str
    status: Status
    detail: str
    sha256: str | None = None
    bytes: int | None = None
    routes: int = 0
    stops: int = 0
    trips: int = 0
    stop_times: int = 0
    services: int = 0
    calendar_start: date | None = None
    calendar_end: date | None = None
    quarantined_trips: int = 0
    quarantine_samples: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()


class NetworkHealth(Record):
    service_date: date
    feeds: tuple[FeedHealth, ...]


def _table(archive: ZipFile, name: str) -> Iterator[list[str]]:
    stream = io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="")
    return csv.reader(stream)


def _columns(reader: Iterator[list[str]]) -> dict[str, int]:
    return {name: index for index, name in enumerate(next(reader))}


def _calendar(archive: ZipFile, day: date) -> tuple[date | None, date | None, int, bool]:
    """Return calendar bounds, the number of services and whether any runs on `day`."""
    names = set(archive.namelist())
    start = end = None
    services: set[str] = set()
    covered = False
    if "calendar.txt" in names:
        reader = _table(archive, "calendar.txt")
        columns = _columns(reader)
        for row in reader:
            first, last = (
                service_date(row[columns["start_date"]]),
                service_date(row[columns["end_date"]]),
            )
            start = first if start is None else min(start, first)
            end = last if end is None else max(end, last)
            services.add(row[columns["service_id"]])
            if first <= day <= last and row[columns[WEEKDAYS[day.weekday()]]] == "1":
                covered = True
    if "calendar_dates.txt" in names:
        reader = _table(archive, "calendar_dates.txt")
        columns = _columns(reader)
        for row in reader:
            services.add(row[columns["service_id"]])
            if service_date(row[columns["date"]]) == day and row[columns["exception_type"]] == "1":
                covered = True
    return start, end, len(services), covered


def _trips(archive: ZipFile, known_stops: set[str]) -> tuple[int, list[str]]:
    """Count stop times and list trips that cannot be routed."""
    reader = _table(archive, "stop_times.txt")
    columns = _columns(reader)
    trip, arrival, departure, stop = (
        columns["trip_id"],
        columns["arrival_time"],
        columns["departure_time"],
        columns["stop_id"],
    )
    calls: dict[str, int] = defaultdict(int)
    last: dict[str, int] = {}
    broken: set[str] = set()
    total = 0
    for row in reader:
        total += 1
        key = row[trip]
        calls[key] += 1
        if row[stop] not in known_stops:
            broken.add(key)
            continue
        try:
            first, second = service_second(row[arrival]), service_second(row[departure])
        except ValueError:
            broken.add(key)
            continue
        if not last.get(key, -1) <= first <= second:
            broken.add(key)
        last[key] = second
    broken.update(key for key, count in calls.items() if count < 2)
    return total, sorted(broken)


def inspect_feed(root: Path, feed: Feed, day: date) -> FeedHealth:
    def unavailable(detail: str, **extra: object) -> FeedHealth:
        return FeedHealth(
            id=feed.id,
            mode=feed.mode,
            status="unavailable",
            detail=detail,
            **extra,  # pyright: ignore[reportArgumentType]
        )

    path = root / f"{feed.id}.zip"
    if feed.sha256 is None or not path.exists():
        return unavailable(
            "No archive is pinned. The official URL did not return a GTFS archive when checked."
        )
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != feed.sha256:
        return unavailable("The archive does not match its pinned checksum.", sha256=digest)
    try:
        archive = ZipFile(io.BytesIO(data))
    except BadZipFile:
        return unavailable("The file is not a zip archive.", sha256=digest, bytes=len(data))
    with archive:
        missing = [name for name in REQUIRED if name not in archive.namelist()]
        if missing:
            return unavailable(f"Missing {', '.join(missing)}.", sha256=digest, bytes=len(data))
        reader = _table(archive, "stops.txt")
        columns = _columns(reader)
        stops = {row[columns["stop_id"]] for row in reader}
        route_count = sum(1 for _ in _table(archive, "routes.txt")) - 1
        trip_count = sum(1 for _ in _table(archive, "trips.txt")) - 1
        calls, broken = _trips(archive, stops)
        start, end, services, covered = _calendar(archive, day)
        assumptions: list[str] = []
        if "frequencies.txt" in archive.namelist():
            assumptions.append("frequencies.txt is not expanded; headway trips are ignored.")
        if covered:
            status: Status = "ok"
            detail = "The calendar covers the service day."
        elif feed.calendar_policy == "project_weekdays":
            status = "projected_calendar"
            detail = "The published calendar does not cover the service day."
            assumptions.append(
                f"The weekly pattern is repeated on {day.isoformat()}. The operator published "
                f"{start} to {end}. This is an assumption, not a timetable."
            )
        else:
            status = "stale_calendar"
            detail = "The published calendar does not cover the service day."
        return FeedHealth(
            id=feed.id,
            mode=feed.mode,
            status=status,
            detail=detail,
            sha256=digest,
            bytes=len(data),
            routes=route_count,
            stops=len(stops),
            trips=trip_count,
            stop_times=calls,
            services=services,
            calendar_start=start,
            calendar_end=end,
            quarantined_trips=len(broken),
            quarantine_samples=tuple(broken[:SAMPLE_LIMIT]),
            assumptions=tuple(assumptions),
        )


def network_health(root: Path, day: date) -> NetworkHealth:
    return NetworkHealth(
        service_date=day, feeds=tuple(inspect_feed(root, feed, day) for feed in feed_specs(root))
    )
