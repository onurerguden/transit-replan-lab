import asyncio
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from test_api_runs import wait

from trl.api.app import create_app


def test_errors_are_problem_details(tmp_path: Path) -> None:
    app = create_app(tmp_path / "runs.sqlite")
    with TestClient(app, raise_server_exceptions=False) as client:
        missing = client.get("/v1/runs/nope")
        wrong_method = client.put("/v1/runs")
        unknown_route = client.get("/v2/anything")
        invalid = client.post(
            "/v1/runs",
            json={"scenario": "secret-value"},
            headers={"Idempotency-Key": "k"},
        )
        for response, status in ((missing, 404), (wrong_method, 405), (unknown_route, 404)):
            assert response.status_code == status
            assert response.headers["content-type"] == "application/problem+json"
            assert response.json()["instance"].startswith("/")
        body = invalid.json()
        assert invalid.status_code == 422 and body["errors"][0]["field"].endswith("scenario")
        assert "secret-value" not in invalid.text


def test_unhandled_failures_hide_internals(tmp_path: Path) -> None:
    app = create_app(tmp_path / "runs.sqlite")
    with TestClient(app, raise_server_exceptions=False) as client:
        runs = app.state.service

        def explode(*_: object, **__: object) -> None:
            raise RuntimeError("database path /private/secret")

        runs.new_run = explode
        response = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "k"})
    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert "secret" not in response.text


def test_creating_a_run_returns_its_location(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "runs.sqlite")) as client:
        response = client.post("/v1/runs", json={}, headers={"Idempotency-Key": "k"})
        assert response.headers["location"] == f"/v1/runs/{response.json()['run_id']}"
        assert wait(client, response.json()["run_id"]).status == "ready"


def test_the_stream_stays_open_while_a_clarification_is_pending(tmp_path: Path) -> None:
    async def exercise() -> None:
        app = create_app(tmp_path / "runs.sqlite")
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://t"
            ) as client,
        ):
            headers = {"Idempotency-Key": "a"}
            run = (
                await client.post("/v1/runs", json={"workflow": "vnext"}, headers=headers)
            ).json()
            await client.post(
                f"/v1/runs/{run['run_id']}/disruptions",
                json={"version": 0, "notice": "Konak İskele tram stop closed until 10:00."},
                headers={"Idempotency-Key": "b"},
            )
            kinds: list[str] = []

            async def read() -> None:
                async with client.stream("GET", f"/v1/runs/{run['run_id']}/events") as stream:
                    async for line in stream.aiter_lines():
                        if line.startswith("data:"):
                            kinds.append(line)

            try:
                await asyncio.wait_for(read(), timeout=3)
                finished = True
            except TimeoutError:
                finished = False
            assert not finished, "the stream closed at clarification"
            replay = await client.get(f"/v1/runs/{run['run_id']}/events?follow=false")
            assert "clarification" in replay.text

    asyncio.run(exercise())
