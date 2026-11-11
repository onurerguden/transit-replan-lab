import time
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from trl.api.app import create_app
from trl.contracts import CreateRun, Disrupt, RunView
from trl.orchestration import RunService
from trl.scenarios import load_scenario
from trl.storage import RunStore


def wait(client: TestClient, run_id: str) -> RunView:
    for _ in range(150):
        response = client.get(f"/v1/runs/{run_id}")
        view = RunView.model_validate(response.json())
        if view.status != "planning":
            return view
        time.sleep(0.02)
    raise AssertionError("Run did not leave planning state.")


def test_commands_and_event_resume(tmp_path: Path) -> None:
    app = create_app(tmp_path / "runs.sqlite")
    with TestClient(app) as client:
        start = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "start"})
        assert start.status_code == 201
        run_id = start.json()["run_id"]
        assert client.post("/v1/runs", json={}, headers={"Idempotency-Key": "start"}).json() == (
            start.json()
        )
        url = f"/v1/runs/{run_id}/disruptions"
        body = {"version": 0, "notice": load_scenario().notice}
        headers = {"Idempotency-Key": "close"}
        first = client.post(url, json=body, headers=headers)
        assert first.status_code == 202
        assert client.post(url, json=body, headers=headers).json() == first.json()
        conflict = client.post(url, json={**body, "notice": "other"}, headers=headers)
        assert conflict.status_code == 409
        assert conflict.headers["content-type"] == "application/problem+json"
        assert client.post(url, json=body, headers={"Idempotency-Key": "old"}).status_code == 409

        view = wait(client, run_id)
        assert view.status == "verified"
        assert len(view.votes) == 2
        assert view.verified_offer == view.offers[0].id

        path = f"/v1/runs/{run_id}/events"
        complete = client.get(path).text
        ids = [line.split(" ", 1)[1] for line in complete.splitlines() if line.startswith("id: ")]
        assert len(ids) == len(set(ids)) and len(ids) >= 6
        resumed = client.get(path, headers={"Last-Event-ID": ids[1]}).text
        assert [
            line.split(" ", 1)[1] for line in resumed.splitlines() if line.startswith("id: ")
        ] == ids[2:]


def test_reopens_a_persisted_queued_run(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    scenario = load_scenario()
    run_store = RunStore(path)
    start = run_store.create(CreateRun(), "start", scenario, None)
    run_store.command(start.run_id, "close", Disrupt(version=0, notice=scenario.notice))
    with TestClient(create_app(path)) as client:
        assert wait(client, start.run_id).status == "verified"


def test_interrupt_resumes_after_application_restart(tmp_path: Path) -> None:
    path = tmp_path / "runs.sqlite"
    with TestClient(create_app(path)) as client:
        start = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "start"})
        run_id = start.json()["run_id"]
        assert (
            client.post(
                f"/v1/runs/{run_id}/disruptions",
                json={"version": 0, "notice": "Konak is closed from 08:24 to 10:00."},
                headers={"Idempotency-Key": "close"},
            ).status_code
            == 202
        )
        assert wait(client, run_id).status == "clarification"
    app = create_app(path)
    with TestClient(app) as client:
        service = cast("RunService", app.state.service)
        assert service.store.read(run_id).question
        assert (
            client.post(
                f"/v1/runs/{run_id}/clarifications",
                json={"version": 1, "answer": "Konak İskele tram"},
                headers={"Idempotency-Key": "answer"},
            ).status_code
            == 202
        )
        assert wait(client, run_id).status == "verified"


def test_process_death_recovers_last_durable_node(tmp_path: Path) -> None:
    import subprocess
    import sys

    path = tmp_path / "runs.sqlite"
    scenario = load_scenario()
    store = RunStore(path)
    run = store.create(CreateRun(), "start", scenario, None)
    receipt = store.command(run.run_id, "close", Disrupt(version=0, notice=scenario.notice))
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio
import os
import signal
import sys
from pathlib import Path
from trl.contracts import Receipt
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.storage import RunStore

class InterruptedService(RunService):
    def search(self, state):
        os.kill(os.getpid(), signal.SIGKILL)

service = InterruptedService(RunStore(Path(sys.argv[1])), load_schedule())
asyncio.run(service.execute(Receipt.model_validate_json(sys.argv[2])))
""",
            str(path),
            receipt.model_dump_json(),
        ],
        check=False,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == -9, result.stderr
    assert store.has_step(run.run_id, 1, "ingest")
    assert not store.has_step(run.run_id, 1, "search")
    with TestClient(create_app(path)) as client:
        assert wait(client, run.run_id).status == "verified"
    assert sum(event.kind == "incident" for event in store.events(run.run_id, 0)) == 1
