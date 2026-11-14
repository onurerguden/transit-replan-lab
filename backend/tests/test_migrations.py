import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

import pytest

from trl import migrations
from trl.contracts import Disrupt, RunView
from trl.migrations import LATEST, SchemaTooNew, migrate, schema_version
from trl.storage import RunStore

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED: dict[str, dict[str, Any]] = json.loads((FIXTURES / "v1_2_0.expected.json").read_text())


def v1_2_0_database(path: Path) -> Path:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript((FIXTURES / "v1_2_0.sql").read_text())
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    return path


def contains(actual: Any, expected: Any) -> bool:
    """Whether `actual` holds everything in `expected`. New fields may appear."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains(actual[key], value)
            for key, value in expected.items()  # pyright: ignore[reportUnknownVariableType]
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)  # pyright: ignore[reportUnknownArgumentType]
            and all(contains(a, e) for a, e in zip(actual, expected, strict=True))  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        )
    return actual == expected


def test_fixture_comes_from_release_code() -> None:
    assert {name: item["view"]["status"] for name, item in EXPECTED.items()} == {
        "abstained": "abstained",
        "clarification": "clarification",
        "model_error": "model_error",
        "planning_pending_call": "planning",
        "superseded": "planning",
        "verified": "verified",
    }


def test_upgrade_preserves_views_events_and_receipts(tmp_path: Path) -> None:
    path = v1_2_0_database(tmp_path / "runs.sqlite")
    store = RunStore(path)
    assert schema_version(sqlite3.connect(path)) == LATEST
    interrupted = {"planning_pending_call", "superseded"}
    for name, item in EXPECTED.items():
        view = json.loads(store.view(item["run_id"]).model_dump_json())
        old = item["view"]
        if name in interrupted:
            assert (view["status"], view["error"]) == ("system_error", "upgrade_interrupted")
            old = {**old, "status": "system_error", "error": "upgrade_interrupted"}
        assert contains(view, old), name
        events = [json.loads(event.model_dump_json()) for event in store.events(item["run_id"], 0)]
        kept = [{k: v for k, v in e.items() if k != "seq"} for e in events[: len(item["events"])]]
        assert kept == [{k: v for k, v in e.items() if k != "seq"} for e in item["events"]], name
        assert len(events) == len(item["events"]) + (1 if name in interrupted else 0)
    # Idempotent receipts survive: the same key and body return the original receipt.
    replay = store.command(
        EXPECTED["verified"]["run_id"],
        "report",
        Disrupt.model_validate(
            {"version": 0, "notice": RunView.model_validate(EXPECTED["verified"]["view"]).notice}
        ),
    )
    assert replay.run_id == EXPECTED["verified"]["run_id"] and replay.version == 1


def test_upgrading_twice_is_a_no_op_and_keeps_a_backup(tmp_path: Path) -> None:
    path = v1_2_0_database(tmp_path / "runs.sqlite")
    assert migrate(path) == [3]
    assert migrate(path) == []
    backup = migrations.backup_path(path, 2)
    assert backup.exists()
    with closing(sqlite3.connect(backup)) as connection:
        assert schema_version(connection) == 2


def test_a_failed_migration_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = v1_2_0_database(tmp_path / "runs.sqlite")

    def explode(connection: sqlite3.Connection) -> None:
        migrations._leases(connection)  # pyright: ignore[reportPrivateUsage]
        raise RuntimeError("boom")

    monkeypatch.setattr(
        migrations,
        "MIGRATIONS",
        (*migrations.MIGRATIONS[:2], migrations.Migration(3, "bad", explode)),
    )
    with pytest.raises(RuntimeError, match="boom"):
        migrate(path)
    with closing(sqlite3.connect(path)) as connection:
        assert schema_version(connection) == 2
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
        assert "leases" not in tables
        assert (
            connection.execute("SELECT count(*) FROM runs WHERE status='planning'").fetchone()[0]
            == 2
        )
    assert migrations.backup_path(path, 2).exists()


def test_a_newer_schema_is_refused_and_untouched(tmp_path: Path) -> None:
    path = tmp_path / "newer.sqlite"
    RunStore(path)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(f"PRAGMA user_version = {LATEST + 1}")
        connection.commit()
    with pytest.raises(SchemaTooNew):
        migrate(path)
    with closing(sqlite3.connect(path)) as connection:
        assert schema_version(connection) == LATEST + 1


def test_a_fresh_database_reaches_the_latest_schema(tmp_path: Path) -> None:
    path = tmp_path / "fresh.sqlite"
    assert migrate(path) == [1, 2, 3]
    assert not migrations.backup_path(path, 0).exists()


def test_an_upgraded_clarification_can_still_be_answered(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient
    from test_api_runs import wait

    from trl.api.app import create_app

    path = v1_2_0_database(tmp_path / "runs.sqlite")
    item = EXPECTED["clarification"]
    question = item["view"]["evidence"]["intake"]["question"]
    with TestClient(create_app(path)) as client:
        response = client.post(
            f"/v1/runs/{item['run_id']}/clarifications",
            json={"version": 1, "question_id": question["id"], "answer": "08:24"},
            headers={"Idempotency-Key": "after-upgrade"},
        )
        assert response.status_code == 202, response.text
        outcome = wait(client, item["run_id"])
    assert outcome.status == "verified" and len(outcome.incidents) == 1
    # The settled revision left no execution checkpoint behind.
    checkpoints = path.with_name("runs.checkpoints.sqlite")
    # The worker deletes the thread right after it settles the run, so allow it a moment.
    remaining = -1
    for _ in range(100):
        with closing(sqlite3.connect(checkpoints)) as connection:
            remaining = connection.execute("SELECT count(*) FROM checkpoints").fetchone()[0]
        if remaining == 0:
            break
        time.sleep(0.05)
    assert remaining == 0
