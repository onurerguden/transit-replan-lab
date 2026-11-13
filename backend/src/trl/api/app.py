"""Local simulation HTTP API and replayable event stream."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from trl import __version__, metrics
from trl.api import middleware
from trl.api.problems import install as install_problems
from trl.contracts import Clarify, CreateRun, Disrupt, Network, Receipt, Retract, Retry, RunView
from trl.gtfs import load_schedule
from trl.lifecycle import SETTLED
from trl.migrations import LATEST, schema_version
from trl.observability import configure_observability, shutdown_observability
from trl.orchestration import RunService
from trl.settings import get_settings
from trl.storage import RunStore

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


class Health(BaseModel):
    status: str = "ok"


def service(request: Request) -> RunService:
    return cast("RunService", request.app.state.service)


Service = Annotated[RunService, Depends(service)]


def current_run(run_id: str, runs: Service) -> RunView:
    return runs.store.view(run_id)


CurrentRun = Annotated[RunView, Depends(current_run)]


async def stream(
    view: RunView, runs: RunService, cursor: int, follow: bool, first: bool
) -> AsyncIterator[ServerSentEvent]:
    """Replay committed events, then follow new ones until the revision settles."""
    while True:
        batch = await asyncio.to_thread(runs.store.events, view.id, cursor)
        for event in batch:
            cursor = event.seq
            # Tell the browser how long to wait before it reconnects.
            yield ServerSentEvent(id=str(event.seq), data=event, retry=3000 if first else None)
            first = False
        if batch:
            continue
        if not follow:
            break
        state = await asyncio.to_thread(runs.store.read, view.id)
        if state.status in SETTLED or state.status == "ready":
            # A terminal update and its event commit together, so one more read is final.
            if not await asyncio.to_thread(runs.store.events, view.id, cursor):
                break
            continue
        # Commits in this process wake the stream. Other processes are picked up by polling.
        await runs.wait_for_change(2.0)


def create_app(path: Path | None = None) -> FastAPI:
    """Build the application. Run it with `uvicorn --factory trl.api.app:create_app`."""
    database = path or get_settings().database

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configure_observability()
        runs = RunService(RunStore(database), load_schedule())
        await runs.configure_default_operator()
        app.state.service = runs
        try:
            async with runs.workers():
                yield
        finally:
            shutdown_observability()

    app = FastAPI(title="Transit Replan Lab", version=__version__, lifespan=lifespan)

    install_problems(app)
    middleware.install(app, get_settings().rate_limit)
    if get_settings().otel_endpoint:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz,readyz,metrics")

    @app.get("/healthz")
    async def health() -> Health:
        return Health()

    @app.get("/readyz")
    async def ready(runs: Service) -> Response:
        """Ready when the database answers at the current schema and the timetable is loaded."""

        def check() -> dict[str, object]:
            with closing(runs.store.connect()) as connection:
                version = schema_version(connection)
            return {"schema": version, "stops": len(runs.schedule.stops)}

        try:
            facts = await asyncio.to_thread(check)
        except Exception:  # noqa: BLE001
            return JSONResponse({"status": "unavailable"}, status_code=503)
        ok = facts["schema"] == LATEST and bool(facts["stops"])
        return JSONResponse(
            {"status": "ok" if ok else "unavailable", **facts}, status_code=200 if ok else 503
        )

    @app.get("/metrics", include_in_schema=False)
    async def scrape() -> Response:
        return Response(metrics.render(), media_type="text/plain; version=0.0.4")

    @app.get("/v1/network")
    def network(runs: Service) -> Network:
        return runs.network()

    @app.post("/v1/runs", status_code=201)
    def new_run(body: CreateRun, key: IdempotencyKey, runs: Service, response: Response) -> Receipt:
        receipt = runs.new_run(body, key)
        response.headers["Location"] = f"/v1/runs/{receipt.run_id}"
        return receipt

    @app.get("/v1/runs/{run_id}", response_model_exclude_unset=True)
    def run(view: CurrentRun) -> RunView:
        return view

    @app.post("/v1/runs/{run_id}/disruptions", status_code=202)
    async def disruption(
        run_id: str,
        body: Disrupt,
        key: IdempotencyKey,
        runs: Service,
    ) -> Receipt:
        receipt = await asyncio.to_thread(runs.store.command, run_id, key, body)
        runs.enqueue(receipt)
        return receipt

    @app.post("/v1/runs/{run_id}/clarifications", status_code=202)
    async def clarification(
        run_id: str,
        body: Clarify,
        key: IdempotencyKey,
        runs: Service,
    ) -> Receipt:
        receipt = await asyncio.to_thread(runs.store.command, run_id, key, body)
        runs.enqueue(receipt)
        return receipt

    @app.post("/v1/runs/{run_id}/retractions", status_code=202)
    async def retraction(
        run_id: str,
        body: Retract,
        key: IdempotencyKey,
        runs: Service,
    ) -> Receipt:
        receipt = await asyncio.to_thread(runs.store.command, run_id, key, body)
        runs.enqueue(receipt)
        return receipt

    @app.post("/v1/runs/{run_id}/retries", status_code=202)
    async def retry(
        run_id: str,
        body: Retry,
        key: IdempotencyKey,
        runs: Service,
    ) -> Receipt:
        receipt = await asyncio.to_thread(runs.store.command, run_id, key, body)
        runs.enqueue(receipt)
        return receipt

    @app.get("/v1/runs/{run_id}/events", response_class=EventSourceResponse)
    async def events(
        view: CurrentRun,
        runs: Service,
        last: Annotated[int, Header(alias="Last-Event-ID", ge=0)] = 0,
        after: Annotated[int, Query(ge=0)] = 0,
        follow: bool = True,
    ) -> AsyncIterator[ServerSentEvent]:
        cursor = max(last, after)
        first = True
        metrics.STREAMS.inc()
        try:
            async for item in stream(view, runs, cursor, follow, first):
                yield item
        finally:
            metrics.STREAMS.dec()

    return app
