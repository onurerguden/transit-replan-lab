from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api_runs import wait

from trl import metrics
from trl.api.app import create_app
from trl.api.middleware import TokenBucket
from trl.scenarios import load_scenario
from trl.settings import get_settings


def test_readiness_reports_the_schema_and_the_timetable(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
        response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["schema"] >= 3 and body["stops"] > 40


def test_metrics_count_requests_runs_and_search_work(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
        run_id = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "a"}).json()["run_id"]
        client.post(
            f"/v1/runs/{run_id}/disruptions",
            json={"version": 0, "notice": load_scenario().notice},
            headers={"Idempotency-Key": "b"},
        )
        assert wait(client, run_id).status == "verified"
        text = client.get("/metrics").text
    assert 'trl_http_requests_total{method="POST",route="/v1/runs",status="201"}' in text
    assert 'trl_runs_settled_total{status="verified"}' in text
    assert "trl_search_work_units_count" in text and "trl_http_request_seconds_bucket" in text


def test_responses_carry_security_headers(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
        headers = client.get("/healthz").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"


def test_the_token_bucket_refills_over_time() -> None:
    now = [0.0]
    bucket = TokenBucket(60, clock=lambda: now[0])
    allowed = [bucket.take("a") is None for _ in range(20)]
    assert allowed[: bucket.burst] == [True] * bucket.burst and not all(allowed)
    assert bucket.take("other") is None
    now[0] += 5
    assert bucket.take("a") is None


def test_the_rate_limit_answers_with_a_problem_and_retry_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRL_RATE_LIMIT", "8")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
            statuses = [
                client.post("/v1/runs", json={}, headers={"Idempotency-Key": f"k{i}"}).status_code
                for i in range(6)
            ]
            limited = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "z"})
    finally:
        get_settings.cache_clear()
    assert 429 in statuses and limited.status_code == 429
    assert limited.headers["content-type"] == "application/problem+json"
    assert int(limited.headers["retry-after"]) >= 1
    assert metrics.RATE_LIMITED._value.get() >= 1  # pyright: ignore[reportPrivateUsage]
