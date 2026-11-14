from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from trl.api.app import create_app
from trl.settings import get_settings

BODY = {"a_stop": "metro:4", "a_ready": 30240, "b_stop": "tram:8", "b_ready": 30540,
        "destination": "tram:3", "meeting_start": 30600, "meeting_end": 36000}  # fmt: skip


def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, network: str) -> TestClient:
    monkeypatch.setenv("TRL_NETWORK", network)
    monkeypatch.setenv("TRL_CACHE", str(tmp_path / "cache"))
    get_settings.cache_clear()
    return TestClient(create_app(tmp_path / "runs.sqlite"))


def test_the_core_network_answers_a_meeting_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        with client(tmp_path, monkeypatch, "core") as http:
            response = http.post("/v1/route", json=BODY)
            unknown = http.post("/v1/route", json={**BODY, "a_stop": "bus:none"})
    finally:
        get_settings.cache_clear()
    assert response.status_code == 200
    body = response.json()
    assert body["network"] == "core" and body["status"] == "feasible" and body["offers"]
    assert body["offers"][0]["meeting"] >= 30600
    assert unknown.status_code == 422
    assert unknown.headers["content-type"] == "application/problem+json"


@pytest.mark.deep
def test_the_full_network_answers_or_says_it_is_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        with client(tmp_path, monkeypatch, "full") as http:
            response = http.post("/v1/route", json=BODY)
            bus = http.post("/v1/route", json={**BODY, "a_stop": "bus:10368"})
    finally:
        get_settings.cache_clear()
    assert response.json()["network"] == "full"
    assert response.json()["status"] in {"feasible", "infeasible", "search_incomplete"}
    assert bus.status_code == 200
