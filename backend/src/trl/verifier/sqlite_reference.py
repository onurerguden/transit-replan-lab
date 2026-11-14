"""A timetable the verifier reads from the raw archives, with no code shared with the router.

The archives are loaded into an indexed SQLite database by this module's own reader. Trips and
stops are fetched on demand, so a plan on the full network is checked without building the
router's arrays or objects for 60,000 trips.
"""

import csv
import io
import sqlite3
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from trl.domain import Stop, StopTime, Transfer, Trip

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def seconds(value: str) -> int:
    hour, minute, second = (int(part) for part in value.split(":"))
    return hour * 3600 + minute * 60 + second


def build(archives: Mapping[str, Path], database: Path, projected: frozenset[str]) -> None:
    """Load `feed id -> archive` into SQLite. Feeds in `projected` repeat their weekly pattern."""
    connection = sqlite3.connect(database)
    connection.executescript(
        """CREATE TABLE stops (id TEXT PRIMARY KEY, name TEXT, lon REAL, lat REAL, access INT);
           CREATE TABLE trips (id TEXT PRIMARY KEY, route TEXT, service TEXT, access INT);
           CREATE TABLE calls (trip TEXT, seq INT, stop TEXT, arr INT, dep INT, pick INT, drop_ INT,
                               PRIMARY KEY (trip, seq));
           CREATE TABLE services (id TEXT PRIMARY KEY, first INT, last INT, days TEXT, repeat INT);
           CREATE TABLE exceptions (service TEXT, day INT, runs INT, PRIMARY KEY (service, day));"""
    )
    for feed, path in archives.items():
        with ZipFile(path) as archive:
            names = set(archive.namelist())

            def rows(name: str, archive: ZipFile = archive) -> Iterator[dict[str, str]]:
                with io.TextIOWrapper(archive.open(name), encoding="utf-8-sig", newline="") as f:
                    yield from csv.DictReader(f)

            connection.executemany(
                "INSERT OR REPLACE INTO stops VALUES (?,?,?,?,?)",
                (
                    (
                        f"{feed}:{r['stop_id']}",
                        r["stop_name"].strip(),
                        float(r["stop_lon"]),
                        float(r["stop_lat"]),
                        {"1": 1, "2": 0}.get(r.get("wheelchair_boarding", ""), -1),
                    )
                    for r in rows("stops.txt")
                ),
            )
            connection.executemany(
                "INSERT INTO trips VALUES (?,?,?,?)",
                (
                    (
                        f"{feed}:{r['trip_id']}",
                        f"{feed}:{r['route_id']}",
                        f"{feed}:{r['service_id']}",
                        {"1": 1, "2": 0}.get(r.get("wheelchair_accessible", ""), -1),
                    )
                    for r in rows("trips.txt")
                ),
            )
            connection.executemany(
                "INSERT INTO calls VALUES (?,?,?,?,?,?,?)",
                (
                    (
                        f"{feed}:{r['trip_id']}",
                        int(r["stop_sequence"]),
                        f"{feed}:{r['stop_id']}",
                        seconds(r["arrival_time"]),
                        seconds(r["departure_time"]),
                        int((r.get("pickup_type") or "0") == "0"),
                        int((r.get("drop_off_type") or "0") == "0"),
                    )
                    for r in rows("stop_times.txt")
                ),
            )
            if "calendar.txt" in names:
                connection.executemany(
                    "INSERT INTO services VALUES (?,?,?,?,?)",
                    (
                        (
                            f"{feed}:{r['service_id']}",
                            datetime.strptime(r["start_date"], "%Y%m%d").toordinal(),
                            datetime.strptime(r["end_date"], "%Y%m%d").toordinal(),
                            "".join(r[day] for day in WEEKDAYS),
                            int(feed in projected),
                        )
                        for r in rows("calendar.txt")
                    ),
                )
            if "calendar_dates.txt" in names:
                connection.executemany(
                    "INSERT OR REPLACE INTO exceptions VALUES (?,?,?)",
                    (
                        (
                            f"{feed}:{r['service_id']}",
                            datetime.strptime(r["date"], "%Y%m%d").toordinal(),
                            int(r["exception_type"] == "1"),
                        )
                        for r in rows("calendar_dates.txt")
                    ),
                )
    connection.execute("CREATE INDEX calls_stop ON calls(stop)")
    connection.commit()
    connection.close()


class _Stops(Mapping[str, Stop]):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __getitem__(self, key: str) -> Stop:
        row = self.connection.execute("SELECT * FROM stops WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return Stop(
            id=row[0],
            name=row[1],
            longitude=row[2],
            latitude=row[3],
            accessible=None if row[4] == -1 else bool(row[4]),
        )

    def __iter__(self) -> Iterator[str]:
        return (row[0] for row in self.connection.execute("SELECT id FROM stops"))

    def __len__(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM stops").fetchone()[0])


class _Trips(Mapping[str, Trip]):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __getitem__(self, key: str) -> Trip:
        row = self.connection.execute("SELECT * FROM trips WHERE id=?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        calls = tuple(
            StopTime(stop=s, arrival=a, departure=d, pickup=bool(p), dropoff=bool(o))
            for s, a, d, p, o in self.connection.execute(
                "SELECT stop, arr, dep, pick, drop_ FROM calls WHERE trip=? ORDER BY seq", (key,)
            )
        )
        return Trip(
            id=row[0],
            route=row[1],
            service=row[2],
            calls=calls,
            accessible=None if row[3] == -1 else bool(row[3]),
        )

    def __iter__(self) -> Iterator[str]:
        return (row[0] for row in self.connection.execute("SELECT id FROM trips"))

    def __len__(self) -> int:
        return int(self.connection.execute("SELECT count(*) FROM trips").fetchone()[0])


class SqliteReference:
    """Implements `ReferenceTimetable` on top of the loaded database."""

    def __init__(self, database: Path, transfers: tuple[Transfer, ...] = ()) -> None:
        self.connection = sqlite3.connect(database)
        self.stops = _Stops(self.connection)
        self.trips = _Trips(self.connection)
        self.transfers = transfers

    def runs(self, service_id: str, day: date) -> bool:
        ordinal = day.toordinal()
        exception = self.connection.execute(
            "SELECT runs FROM exceptions WHERE service=? AND day=?", (service_id, ordinal)
        ).fetchone()
        if exception is not None:
            return bool(exception[0])
        row = self.connection.execute(
            "SELECT first, last, days, repeat FROM services WHERE id=?", (service_id,)
        ).fetchone()
        if row is None:
            return False
        inside = row[0] <= ordinal <= row[1] or bool(row[3])
        return inside and row[2][day.weekday()] == "1"
