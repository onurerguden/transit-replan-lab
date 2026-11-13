# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""A columnar timetable for the whole network, compiled once per set of archives.

Rows of `stop_times` live in numpy arrays so one query can bound the search with vectorized
passes. Compiled arrays are cached under `.local/cache/timetable/<key>.npz`. The key hashes the
archive checksums, the feed metadata, the transfers and the compiler version.
"""

import csv
import hashlib
import io
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import numpy as np
from numpy.typing import NDArray

from trl.gtfs import Feed, Profile, feed_specs, service_date, service_second

COMPILER_VERSION = "compact-1"
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
Int = NDArray[np.int32]


@dataclass(frozen=True)
class CompactTimetable:
    key: str
    stop_ids: tuple[str, ...]
    stop_names: tuple[str, ...]
    stop_lon: NDArray[np.float64]
    stop_lat: NDArray[np.float64]
    trip_ids: tuple[str, ...]
    trip_routes: tuple[str, ...]
    trip_service: Int
    trip_ptr: Int
    st_stop: Int
    st_arr: Int
    st_dep: Int
    st_pickup: NDArray[np.uint8]
    st_dropoff: NDArray[np.uint8]
    service_ids: tuple[str, ...]
    service_start: Int
    service_end: Int
    service_days: NDArray[np.uint8]
    service_projected: NDArray[np.uint8]
    exception_rows: NDArray[np.int64]  # columns: service, ordinal, runs

    @property
    def trips(self) -> int:
        return len(self.trip_ids)

    @property
    def stop_times(self) -> int:
        return int(self.st_stop.size)

    def active_services(self, day: date) -> NDArray[np.bool_]:
        ordinal = day.toordinal()
        inside = (self.service_start <= ordinal) & (ordinal <= self.service_end)
        weekday = self.service_days[:, day.weekday()] == 1
        active = (inside | (self.service_projected == 1)) & weekday
        for service, when, runs in self.exception_rows:
            if when == ordinal:
                active[service] = bool(runs)
        return active


@dataclass
class Builder:
    stops: dict[str, tuple[str, float, float]] = field(default_factory=dict)
    trip_ids: list[str] = field(default_factory=list)
    trip_routes: list[str] = field(default_factory=list)
    trip_services: list[str] = field(default_factory=list)
    services: dict[str, int] = field(default_factory=dict)
    service_rows: list[tuple[int, int, list[int], int]] = field(default_factory=list)
    exceptions: list[tuple[str, int, int]] = field(default_factory=list)
    calls: list[tuple[int, int, int, int, int, int, int]] = field(default_factory=list)


def cache_key(root: Path, profile: Profile) -> str:
    digest = hashlib.sha256(f"{COMPILER_VERSION}:{profile}".encode())
    for feed in feed_specs(root):
        if profile in feed.profiles and feed.sha256:
            digest.update(feed.model_dump_json().encode())
    digest.update((root / "transfers.json").read_bytes())
    return digest.hexdigest()[:24]


def table(archive: ZipFile, name: str) -> tuple[dict[str, int], Iterator[list[str]]]:
    reader = csv.reader(io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline=""))
    return {title: index for index, title in enumerate(next(reader))}, reader


def compile_timetable(root: Path, profile: Profile = "full") -> CompactTimetable:
    builder = Builder()
    for feed in feed_specs(root):
        path = root / f"{feed.id}.zip"
        if profile not in feed.profiles or not feed.sha256 or not path.exists():
            continue
        with ZipFile(path) as archive:
            read_stops(builder, archive, feed)
            read_trips(builder, archive, feed, profile)
            read_calendar(builder, archive, feed)
            read_calls(builder, archive, feed)
    return assemble(cache_key(root, profile), builder)


def read_stops(builder: Builder, archive: ZipFile, feed: Feed) -> None:
    columns, reader = table(archive, "stops.txt")
    for row in reader:
        builder.stops[f"{feed.id}:{row[columns['stop_id']]}"] = (
            row[columns["stop_name"]].strip(),
            float(row[columns["stop_lon"]]),
            float(row[columns["stop_lat"]]),
        )


def read_trips(builder: Builder, archive: ZipFile, feed: Feed, profile: Profile) -> None:
    columns, reader = table(archive, "trips.txt")
    wanted = set(feed.routes) if profile == "core" else None
    for row in reader:
        if wanted is not None and row[columns["route_id"]] not in wanted:
            continue
        builder.trip_ids.append(f"{feed.id}:{row[columns['trip_id']]}")
        builder.trip_routes.append(f"{feed.id}:{row[columns['route_id']]}")
        builder.trip_services.append(f"{feed.id}:{row[columns['service_id']]}")


def read_calendar(builder: Builder, archive: ZipFile, feed: Feed) -> None:
    projected = int(feed.calendar_policy == "project_weekdays")
    names = set(archive.namelist())
    if "calendar.txt" in names:
        columns, reader = table(archive, "calendar.txt")
        for row in reader:
            builder.services[f"{feed.id}:{row[columns['service_id']]}"] = len(builder.service_rows)
            builder.service_rows.append(
                (
                    service_date(row[columns["start_date"]]).toordinal(),
                    service_date(row[columns["end_date"]]).toordinal(),
                    [int(row[columns[day]]) for day in WEEKDAYS],
                    projected,
                )
            )
    if "calendar_dates.txt" in names:
        columns, reader = table(archive, "calendar_dates.txt")
        for row in reader:
            key = f"{feed.id}:{row[columns['service_id']]}"
            if key not in builder.services:
                builder.services[key] = len(builder.service_rows)
                builder.service_rows.append((1, 0, [0] * 7, 0))
            builder.exceptions.append(
                (
                    key,
                    service_date(row[columns["date"]]).toordinal(),
                    int(row[columns["exception_type"]] == "1"),
                )
            )


def read_calls(builder: Builder, archive: ZipFile, feed: Feed) -> None:
    prefix = f"{feed.id}:"
    trips = {name: index for index, name in enumerate(builder.trip_ids) if name.startswith(prefix)}
    stops = {name: index for index, name in enumerate(builder.stops)}
    columns, reader = table(archive, "stop_times.txt")
    trip, arrival, departure = (
        columns["trip_id"],
        columns["arrival_time"],
        columns["departure_time"],
    )
    stop, sequence = columns["stop_id"], columns["stop_sequence"]
    pickup, dropoff = columns.get("pickup_type"), columns.get("drop_off_type")
    for row in reader:
        index = trips.get(prefix + row[trip])
        if index is None:
            continue
        builder.calls.append(
            (
                index,
                int(row[sequence]),
                stops[prefix + row[stop]],
                service_second(row[arrival]),
                service_second(row[departure]),
                int(pickup is None or row[pickup] in ("", "0")),
                int(dropoff is None or row[dropoff] in ("", "0")),
            )
        )


def assemble(key: str, builder: Builder) -> CompactTimetable:
    names = list(builder.stops)
    calls = np.asarray(builder.calls, dtype=np.int64).reshape(-1, 7)
    order = np.lexsort((calls[:, 1], calls[:, 0]))
    calls = calls[order]
    trip_ptr = np.searchsorted(calls[:, 0], np.arange(len(builder.trip_ids) + 1)).astype(np.int32)
    service_index = np.asarray(
        [builder.services.get(name, -1) for name in builder.trip_services], dtype=np.int32
    )
    rows = builder.service_rows
    return CompactTimetable(
        key=key,
        stop_ids=tuple(names),
        stop_names=tuple(builder.stops[name][0] for name in names),
        stop_lon=np.asarray([builder.stops[name][1] for name in names], dtype=np.float64),
        stop_lat=np.asarray([builder.stops[name][2] for name in names], dtype=np.float64),
        trip_ids=tuple(builder.trip_ids),
        trip_routes=tuple(builder.trip_routes),
        trip_service=service_index,
        trip_ptr=trip_ptr,
        st_stop=calls[:, 2].astype(np.int32),
        st_arr=calls[:, 3].astype(np.int32),
        st_dep=calls[:, 4].astype(np.int32),
        st_pickup=calls[:, 5].astype(np.uint8),
        st_dropoff=calls[:, 6].astype(np.uint8),
        service_ids=tuple(builder.services),
        service_start=np.asarray([row[0] for row in rows], dtype=np.int32),
        service_end=np.asarray([row[1] for row in rows], dtype=np.int32),
        service_days=np.asarray([row[2] for row in rows], dtype=np.uint8).reshape(-1, 7),
        service_projected=np.asarray([row[3] for row in rows], dtype=np.uint8),
        exception_rows=np.asarray(
            [(builder.services[name], when, runs) for name, when, runs in builder.exceptions],
            dtype=np.int64,
        ).reshape(-1, 3),
    )


def save(timetable: CompactTimetable, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {
        name: value for name, value in vars(timetable).items() if isinstance(value, np.ndarray)
    }
    strings = {
        name: list(value) for name, value in vars(timetable).items() if isinstance(value, tuple)
    }
    payload: dict[str, Any] = dict(arrays)
    payload["__strings"] = np.asarray(json.dumps(strings))
    payload["__key"] = np.asarray(timetable.key)
    np.savez(path, **payload)


def load(path: Path) -> CompactTimetable:
    with np.load(path, allow_pickle=False) as data:
        strings = json.loads(str(data["__strings"]))
        arrays = {name: data[name] for name in data.files if not name.startswith("__")}
        return CompactTimetable(
            key=str(data["__key"]),
            **{name: tuple(value) for name, value in strings.items()},
            **arrays,
        )


def get_timetable(root: Path, cache: Path, profile: Profile = "full") -> CompactTimetable:
    path = cache / f"{cache_key(root, profile)}.npz"
    if path.exists():
        return load(path)
    timetable = compile_timetable(root, profile)
    save(timetable, path)
    return timetable
