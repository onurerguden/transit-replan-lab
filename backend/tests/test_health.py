from fastapi.testclient import TestClient

from trl.api.app import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
