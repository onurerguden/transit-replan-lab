"""Back up, restore, check and prune the run database."""

import hashlib
import json
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from trl.contracts import RunBody
from trl.lifecycle import SETTLED
from trl.migrations import IntegrityFailure, SchemaTooNew, check, migrate, schema_version


class RestoreRefused(RuntimeError):
    """The backup is damaged or the target database is in use."""


@dataclass(frozen=True)
class Problem:
    run_id: str | None
    message: str


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_path(backup: Path) -> Path:
    return backup.with_name(f"{backup.name}.manifest.json")


def backup(source: Path, target: Path) -> Path:
    """Write a consistent copy with SQLite's online backup API and a checksum manifest."""
    if target.exists():
        raise FileExistsError(f"{target} already exists.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(target)) as copy:
        origin.backup(copy)
        version = schema_version(copy)
    manifest_path(target).write_text(
        json.dumps({"sha256": sha256(target), "schema_version": version}, indent=2) + "\n"
    )
    return target


def live_leases(path: Path) -> list[str]:
    with closing(sqlite3.connect(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        if "leases" not in tables:
            return []
        return [
            row[0]
            for row in connection.execute(
                "SELECT run_id FROM leases WHERE owner IS NOT NULL AND expires_at > ?",
                (time.time(),),
            )
        ]


def restore(source: Path, target: Path) -> list[int]:
    """Replace the database with a verified backup, then migrate it forward."""
    manifest = json.loads(manifest_path(source).read_text())
    if sha256(source) != manifest["sha256"]:
        raise RestoreRefused("The backup does not match its checksum.")
    with closing(sqlite3.connect(source)) as connection:
        if schema_version(connection) > schema_version_limit():
            raise SchemaTooNew("The backup was written by a newer release.")
        check(connection)
    if target.exists() and (leases := live_leases(target)):
        raise RestoreRefused(f"{len(leases)} run(s) hold a live lease. Stop the service first.")
    staging = target.with_name(f"{target.name}.restoring")
    staging.unlink(missing_ok=True)
    with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(staging)) as copy:
        origin.backup(copy)
    for suffix in ("", "-wal", "-shm"):
        target.with_name(target.name + suffix).unlink(missing_ok=True)
    staging.replace(target)
    return migrate(target)


def schema_version_limit() -> int:
    from trl.migrations import LATEST

    return LATEST


def invariants(path: Path) -> list[Problem]:
    """Application-level checks on top of SQLite's own integrity checks."""
    problems: list[Problem] = []
    with closing(sqlite3.connect(path)) as connection:
        connection.row_factory = sqlite3.Row
        try:
            check(connection)
        except IntegrityFailure as exc:
            problems.append(Problem(None, str(exc)))
        runs = connection.execute("SELECT id, version, status, body FROM runs").fetchall()
        for row in runs:
            run_id = row["id"]
            body = RunBody.model_validate_json(row["body"])
            if (body.version, body.status) != (row["version"], row["status"]):
                problems.append(Problem(run_id, "The run row disagrees with its body."))
            sequence = [
                item[0]
                for item in connection.execute(
                    "SELECT seq FROM events WHERE run_id=? ORDER BY seq", (run_id,)
                )
            ]
            if sequence != sorted(set(sequence)):
                problems.append(Problem(run_id, "Event sequence numbers are not increasing."))
            versions = [
                item[0]
                for item in connection.execute(
                    "SELECT version FROM events WHERE run_id=? ORDER BY seq", (run_id,)
                )
            ]
            if versions != sorted(versions):
                problems.append(Problem(run_id, "Event versions decrease."))
            if body.status == "verified":
                accepted = connection.execute(
                    "SELECT count(DISTINCT rider) FROM votes WHERE run_id=? AND version=? "
                    "AND offer_id=? AND json_extract(body, '$.accepted')=1",
                    (run_id, body.version, body.verified_offer),
                ).fetchone()[0]
                if accepted != 2:
                    problems.append(Problem(run_id, "A verified run lacks two acceptances."))
            lease = connection.execute(
                "SELECT owner, expires_at FROM leases WHERE run_id=?", (run_id,)
            ).fetchone()
            if (
                body.status in SETTLED
                and lease
                and lease["owner"] is not None
                and lease["expires_at"] > time.time()
            ):
                problems.append(Problem(run_id, "A settled run holds a live lease."))
    return problems


def prune(path: Path, *, older_than_days: float, now: float | None = None) -> int:
    """Delete settled runs whose last event is older than the cutoff. Return how many."""
    cutoff = (now if now is not None else time.time()) - older_than_days * 86400
    removed = 0
    with closing(sqlite3.connect(path, isolation_level=None)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" * len(SETTLED))  # only question marks, never values
        stale = [
            row[0]
            for row in connection.execute(
                f"""SELECT r.id FROM runs r WHERE r.status IN ({placeholders})
                    AND (SELECT CAST(strftime('%s', max(recorded_at)) AS INTEGER) FROM events e
                         WHERE e.run_id = r.id) < ?""",  # noqa: S608
                (*sorted(SETTLED), cutoff),
            )
        ]
        for run_id in stale:
            for table in ("votes", "offers", "model_calls", "steps", "events", "leases"):
                connection.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))  # noqa: S608
            connection.execute("DELETE FROM commands WHERE scope LIKE ?", (f"%:{run_id}",))
            connection.execute("DELETE FROM runs WHERE id=?", (run_id,))
            removed += 1
        connection.execute("COMMIT")
    return removed
