"""Local simulation HTTP API and replayable event stream."""

import asyncio
import os
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from trl.contracts import Clarify, CreateRun, Disrupt, Network, Receipt, RunView
from trl.gtfs import load_schedule
from trl.observability import configure_observability
from trl.orchestration import RunService
from trl.storage import Conflict, NotFound, RunStore

IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


class Health(BaseModel):
    status: str = "ok"


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str


def problem(status: int, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        Problem(title=title, status=status, detail=detail).model_dump(),
        status_code=status,
        media_type="application/problem+json",
    )


def service(request: Request) -> RunService:
    return cast("RunService", request.app.state.service)


Service = Annotated[RunService, Depends(service)]


def current_run(run_id: str, runs: Service) -> RunView:
    return runs.store.view(run_id)


CurrentRun = Annotated[RunView, Depends(current_run)]


def create_app(path: Path | None = None) -> FastAPI:
    database = path or Path(os.environ.get("TRL_DB", ".local/state/transit.sqlite"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        configure_observability()
        runs = RunService(RunStore(database), load_schedule())
        await runs.configure_default_operator()
        app.state.service = runs
        async with runs.workers():
            yield

    app = FastAPI(title="Transit Replan Lab", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(NotFound)
    async def missing(_request: Request, exc: NotFound) -> JSONResponse:
        return problem(404, "Run not found", str(exc))

    @app.exception_handler(Conflict)
    async def conflict(_request: Request, exc: Conflict) -> JSONResponse:
        return problem(409, "Command conflict", str(exc))

    @app.exception_handler(RequestValidationError)
    async def invalid(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return problem(422, "Invalid request", "Check the command, version, and required headers.")

    @app.get("/healthz")
    async def health() -> Health:
        return Health()

    @app.get("/v1/network")
    def network(runs: Service) -> Network:
        return runs.network()

    @app.post("/v1/runs", status_code=201)
    def new_run(body: CreateRun, key: IdempotencyKey, runs: Service) -> Receipt:
        return runs.new_run(body, key)

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

    @app.get("/v1/runs/{run_id}/events", response_class=EventSourceResponse)
    async def events(
        view: CurrentRun,
        runs: Service,
        last: Annotated[int, Header(alias="Last-Event-ID", ge=0)] = 0,
        after: Annotated[int, Query(ge=0)] = 0,
        follow: bool = True,
    ) -> AsyncIterator[ServerSentEvent]:
        cursor = max(last, after)
        while True:
            batch = await asyncio.to_thread(runs.store.events, view.id, cursor)
            if not batch and follow:
                state = await asyncio.to_thread(runs.store.read, view.id)
                if state.status != "planning":
                    # A terminal update and its event commit together.
                    batch = await asyncio.to_thread(runs.store.events, view.id, cursor)
                    if not batch:
                        break
            for event in batch:
                cursor = event.seq
                yield ServerSentEvent(id=str(event.seq), data=event)
            if not batch:
                if not follow:
                    break
                await asyncio.sleep(0.15)

    return app


app = create_app()
