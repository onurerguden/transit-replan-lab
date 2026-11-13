from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api_runs import wait

from trl.api.app import create_app
from trl.contracts import Disrupt, EventDraft, RunView
from trl.lifecycle import (
    COMMAND_SOURCES,
    SETTLED,
    IllegalTransition,
    check_command,
    check_worker_transition,
    retryable,
)
from trl.scenarios import load_scenario

NOTICE = load_scenario().notice
SECOND = "Karataş tram stop is closed from 08:00 to 08:10."


def post(client: TestClient, path: str, body: dict[str, object], key: str) -> dict[str, object]:
    response = client.post(path, json=body, headers={"Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()


def start(client: TestClient) -> str:
    response = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "start"})
    return response.json()["run_id"]


def test_workers_cannot_leave_the_table() -> None:
    with pytest.raises(IllegalTransition):
        check_worker_transition("verified", "planning")
    with pytest.raises(IllegalTransition):
        check_worker_transition("planning", "ready")
    for target in SETTLED:
        check_worker_transition("planning", target)


def test_every_command_has_a_source_status() -> None:
    assert COMMAND_SOURCES["clarify"] == {"clarification"}
    with pytest.raises(IllegalTransition):
        check_command("retry", "verified")
    assert retryable("model_error", "model_unavailable")
    assert not retryable("model_error", "request_mismatch")
    assert not retryable("verified", None)


def test_replacing_and_retracting_incidents(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
        run_id = start(client)
        post(client, f"/v1/runs/{run_id}/disruptions", {"version": 0, "notice": NOTICE}, "one")
        first = wait(client, run_id)
        assert first.status == "verified" and len(first.incidents) == 1
        post(client, f"/v1/runs/{run_id}/disruptions", {"version": 1, "notice": SECOND}, "two")
        both = wait(client, run_id)
        assert both.version == 2 and len(both.incidents) == 2

        # Retracting one incident replans with the other without reading a report.
        removed = both.incidents[1].id
        post(
            client,
            f"/v1/runs/{run_id}/retractions",
            {"version": 2, "incident_ids": [removed]},
            "r1",
        )
        remaining = wait(client, run_id)
        assert remaining.version == 3 and remaining.status == "verified"
        assert [item.id for item in remaining.incidents] == [both.incidents[0].id]

        # Retracting the last incident returns to the nominal plan.
        post(
            client,
            f"/v1/runs/{run_id}/retractions",
            {"version": 3, "incident_ids": [remaining.incidents[0].id]},
            "r2",
        )
        nominal = RunView.model_validate(client.get(f"/v1/runs/{run_id}").json())
        assert nominal.status == "ready" and nominal.incidents == () and nominal.offers == ()

        # `replace` drops everything before reading the new report.
        post(client, f"/v1/runs/{run_id}/disruptions", {"version": 4, "notice": NOTICE}, "three")
        wait(client, run_id)
        post(
            client,
            f"/v1/runs/{run_id}/disruptions",
            {"version": 5, "notice": SECOND, "mode": "replace"},
            "four",
        )
        replaced = wait(client, run_id)
        assert len(replaced.incidents) == 1


def test_illegal_commands_are_conflicts(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
        run_id = start(client)
        post(client, f"/v1/runs/{run_id}/disruptions", {"version": 0, "notice": NOTICE}, "one")
        wait(client, run_id)
        for path, body in (
            ("retries", {"version": 1}),
            ("retractions", {"version": 1, "incident_ids": ["missing"]}),
            ("clarifications", {"version": 1, "answer": "08:24"}),
        ):
            response = client.post(
                f"/v1/runs/{run_id}/{path}", json=body, headers={"Idempotency-Key": path}
            )
            assert response.status_code == 409, path
            assert response.headers["content-type"] == "application/problem+json"


def test_a_retryable_failure_can_be_retried(tmp_path: Path) -> None:
    app = create_app(tmp_path / "runs.sqlite")
    with TestClient(app) as client:
        run_id = start(client)
        store = app.state.service.store
        receipt = store.command(
            run_id,
            "report",
            Disrupt(version=0, notice=NOTICE),
        )
        store.step(
            run_id,
            receipt.version,
            "model-error",
            updates={"status": "model_error", "error": "model_unavailable"},
            event=EventDraft(kind="error", role="system", message="The model failed."),
        )
        failed = RunView.model_validate(client.get(f"/v1/runs/{run_id}").json())
        assert failed.status == "model_error" and failed.retryable
        post(client, f"/v1/runs/{run_id}/retries", {"version": failed.version}, "retry")
        again = wait(client, run_id)
        assert again.status == "verified" and again.version == failed.version + 1
