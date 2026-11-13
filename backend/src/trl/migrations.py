"""Numbered schema migrations with a pre-upgrade backup and integrity checks.

`PRAGMA user_version` holds the applied number. Version 2 is the v1.2.0 schema. A database
newer than this code is refused instead of rewritten.
"""

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

BASELINE = (
    """CREATE TABLE IF NOT EXISTS runs (
      id TEXT PRIMARY KEY, version INTEGER NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS commands (
      scope TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, response TEXT NOT NULL,
      PRIMARY KEY (scope, key))""",
    """CREATE TABLE IF NOT EXISTS steps (
      run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL, step TEXT NOT NULL,
      PRIMARY KEY (run_id, version, step))""",
    """CREATE TABLE IF NOT EXISTS events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL,
      recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
      body TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS events_run_seq ON events(run_id, seq)",
    """CREATE TABLE IF NOT EXISTS offers (
      run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL,
      offer_id TEXT NOT NULL, ordinal INTEGER NOT NULL, body TEXT NOT NULL,
      PRIMARY KEY (run_id, version, offer_id))""",
    """CREATE TABLE IF NOT EXISTS votes (
      run_id TEXT NOT NULL, version INTEGER NOT NULL, offer_id TEXT NOT NULL,
      rider TEXT NOT NULL, body TEXT NOT NULL,
      PRIMARY KEY (run_id, version, offer_id, rider),
      FOREIGN KEY (run_id, version, offer_id) REFERENCES offers(run_id, version, offer_id))""",
    """CREATE TABLE IF NOT EXISTS model_calls (
      id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
      version INTEGER NOT NULL, step TEXT NOT NULL, model TEXT NOT NULL, digest TEXT NOT NULL,
      context INTEGER NOT NULL, request_sha256 TEXT NOT NULL DEFAULT '',
      state TEXT NOT NULL DEFAULT 'pending', content TEXT,
      input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
      duration_ms INTEGER NOT NULL DEFAULT 0)""",
    "CREATE INDEX IF NOT EXISTS model_calls_run_version ON model_calls(run_id,version,id)",
)


class SchemaTooNew(RuntimeError):
    """The database was written by a newer release than this one."""


class IntegrityFailure(RuntimeError):
    """The database failed SQLite integrity or foreign key checks after migrating."""


@dataclass(frozen=True)
class Migration:
    number: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


def _baseline(connection: sqlite3.Connection) -> None:
    for statement in BASELINE:
        connection.execute(statement)


def _call_request_digest(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(model_calls)")}
    if "request_sha256" not in columns:
        connection.execute(
            "ALTER TABLE model_calls ADD COLUMN request_sha256 TEXT NOT NULL DEFAULT ''"
        )


def _interrupt_planning_runs(connection: sqlite3.Connection) -> None:
    """Checkpoints move to their own database, so planning runs cannot resume in place."""
    rows = connection.execute(
        "SELECT id, version, body FROM runs WHERE status='planning'"
    ).fetchall()
    for run_id, version, body in rows:
        document = json.loads(body)
        document["status"] = "system_error"
        document["error"] = "upgrade_interrupted"
        connection.execute(
            "UPDATE runs SET status='system_error', body=? WHERE id=?",
            (json.dumps(document, ensure_ascii=False), run_id),
        )
        event = {
            "kind": "error",
            "role": "system",
            "message": "The run was interrupted by a software upgrade. Retry it.",
            "details": {"reason": "upgrade_interrupted"},
        }
        connection.execute(
            "INSERT INTO events (run_id, version, body) VALUES (?,?,?)",
            (run_id, version, json.dumps(event)),
        )


def _leases(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS leases (
             run_id TEXT PRIMARY KEY REFERENCES runs(id),
             version INTEGER NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
             owner TEXT, token INTEGER NOT NULL DEFAULT 0, expires_at REAL NOT NULL DEFAULT 0)"""
    )
    _interrupt_planning_runs(connection)
    # Checkpoints moved to their own database. An answered clarification replays from intake.
    connection.execute("DROP TABLE IF EXISTS writes")
    connection.execute("DROP TABLE IF EXISTS checkpoints")


MIGRATIONS = (
    Migration(1, "baseline tables", _baseline),
    Migration(2, "model call request digest", _call_request_digest),
    Migration(3, "execution leases", _leases),
)
LATEST = MIGRATIONS[-1].number


def schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def backup_path(path: Path, version: int) -> Path:
    return path.with_name(f"{path.name}.pre-v{version}.bak")


def migrate(path: Path) -> list[int]:
    """Bring the database to the latest schema. Return the migrations applied."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, isolation_level=None, timeout=5)) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        current = schema_version(connection)
        if current > LATEST:
            raise SchemaTooNew(
                f"The database has schema version {current}; this release supports up to {LATEST}."
            )
        pending = [item for item in MIGRATIONS if item.number > current]
        if not pending:
            return []
        populated = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        if populated:
            with closing(sqlite3.connect(backup_path(path, current))) as target:
                connection.backup(target)
        applied: list[int] = []
        for item in pending:
            connection.execute("BEGIN IMMEDIATE")
            try:
                item.apply(connection)
                connection.execute(f"PRAGMA user_version = {item.number}")
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise
            applied.append(item.number)
        check(connection)
        return applied


def check(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()[0]
    broken = connection.execute("PRAGMA foreign_key_check").fetchall()
    if result != "ok" or broken:
        raise IntegrityFailure(f"integrity_check={result}; foreign key violations={len(broken)}")
