import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api_runs import wait
from test_migrations import EXPECTED, v1_2_0_database

from trl import dbtools
from trl.api.app import create_app
from trl.contracts import RunView
from trl.migrations import SchemaTooNew, migrate
from trl.scenarios import load_scenario
from trl.storage import RunStore


def completed_database(path: Path) -> str:
    with TestClient(create_app(path)) as client:
        run_id = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "s"}).json()["run_id"]
        client.post(
            f"/v1/runs/{run_id}/disruptions",
            json={"version": 0, "notice": load_scenario().notice},
            headers={"Idempotency-Key": "d"},
        )
        assert wait(client, run_id).status == "verified"
    return run_id


def test_backup_restore_round_trip_keeps_a_completed_revision_readable(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    run_id = completed_database(path)
    before = RunStore(path).view(run_id)
    copy = dbtools.backup(path, tmp_path / "backups" / "runs.bak")
    assert json.loads(dbtools.manifest_path(copy).read_text())["schema_version"] >= 3
    path.unlink()
    for suffix in ("-wal", "-shm"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)
    assert dbtools.restore(copy, path) == []
    after = RunStore(path).view(run_id)
    assert after == before and after.status == "verified"
    assert dbtools.invariants(path) == []


def test_restore_refuses_a_tampered_backup_and_a_live_lease(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    completed_database(path)
    copy = dbtools.backup(path, tmp_path / "runs.bak")
    with closing(sqlite3.connect(copy)) as connection:
        connection.execute("DELETE FROM events")
        connection.commit()
    with pytest.raises(dbtools.RestoreRefused, match="checksum"):
        dbtools.restore(copy, tmp_path / "other.sqlite")

    good = dbtools.backup(path, tmp_path / "good.bak")
    store = RunStore(path)
    run_id = next(iter(store.active()), None)
    assert run_id is None
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE leases SET owner='worker', expires_at=?", (9_999_999_999,))
        connection.commit()
    with pytest.raises(dbtools.RestoreRefused, match="lease"):
        dbtools.restore(good, path)


def test_check_reports_invariant_violations(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    run_id = completed_database(path)
    assert dbtools.invariants(path) == []
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("DELETE FROM votes WHERE run_id=? AND rider='b'", (run_id,))
        connection.commit()
    assert [item.message for item in dbtools.invariants(path)] == [
        "A verified run lacks two acceptances."
    ]


def test_prune_removes_only_old_settled_runs(tmp_path: Path) -> None:
    path = v1_2_0_database(tmp_path / "runs.sqlite")
    migrate(path)
    removed = dbtools.prune(path, older_than_days=0, now=4_000_000_000)
    # The upgrade settled the two planning runs as system_error. Only the clarification stays.
    assert removed == 5
    with closing(sqlite3.connect(path)) as connection:
        remaining = {row[0] for row in connection.execute("SELECT id FROM runs")}
    assert EXPECTED["clarification"]["run_id"] in remaining
    assert EXPECTED["verified"]["run_id"] not in remaining
    assert dbtools.invariants(path) == []
    assert RunView.model_validate_json(
        RunStore(path).view(EXPECTED["clarification"]["run_id"]).model_dump_json()
    )


def test_cli_migrates_checks_and_backs_up(tmp_path: Path) -> None:
    path = v1_2_0_database(tmp_path / "runs.sqlite")

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "trl.cli", "db", "--db", str(path), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    migrated = run("migrate")
    assert migrated.returncode == 0 and json.loads(migrated.stdout) == {"applied": [3]}
    assert run("check").returncode == 0
    assert run("backup", str(tmp_path / "out.bak")).returncode == 0
    assert (tmp_path / "out.bak").exists()


def test_a_newer_backup_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    completed_database(path)
    copy = dbtools.backup(path, tmp_path / "runs.bak")
    with closing(sqlite3.connect(copy)) as connection:
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
    manifest = dbtools.manifest_path(copy)
    manifest.write_text(json.dumps({"sha256": dbtools.sha256(copy), "schema_version": 99}))
    with pytest.raises(SchemaTooNew):
        dbtools.restore(copy, tmp_path / "target.sqlite")
