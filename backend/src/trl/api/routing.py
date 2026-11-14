"""A stateless route endpoint that serves the compiled network, core or full."""

import asyncio
import json
from datetime import date
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from trl.api.problems import problem
from trl.contracts import RouteAnswer, RouteQuery
from trl.domain import Constraint, Scenario, StopClosure
from trl.gtfs import DATA_ROOT
from trl.routing import Budget, SearchIncomplete, SearchStats
from trl.scenarios import load_scenario
from trl.settings import get_settings
from trl.timetable.compact import CompactTimetable, get_timetable
from trl.timetable.footpaths import Footpaths, from_transfers, generate
from trl.timetable.query import route

router = APIRouter()
DEADLINE_S = 20.0


def load(network: Literal["core", "full"]) -> tuple[CompactTimetable, Footpaths]:
    root = DATA_ROOT / "gtfs"
    table = get_timetable(root, get_settings().cache, "full" if network == "full" else "core")
    documented = {
        (item["origin"], item["destination"]): item["duration"]
        for item in json.loads((root / "transfers.json").read_text())
    }
    if network == "core":
        return table, from_transfers(table.stop_ids, documented)
    paths = generate(
        list(table.stop_ids),
        table.stop_lon.tolist(),
        table.stop_lat.tolist(),
        documented=documented,
    )
    return table, paths


def solve(
    table: CompactTimetable,
    paths: Footpaths,
    query: RouteQuery,
    day: date,
    network: Literal["core", "full"],
) -> RouteAnswer:
    ready = min(query.a_ready, query.b_ready)
    scenario = Scenario(
        id="route",
        service_date=day,
        a=Constraint(stop=query.a_stop, ready=query.a_ready, wait_limit=query.wait_limit),
        b=Constraint(stop=query.b_stop, ready=query.b_ready, wait_limit=query.wait_limit),
        destinations=(query.destination,),
        meeting_start=query.meeting_start if query.meeting_start is not None else ready,
        meeting_end=query.meeting_end or ready + 7200,
        notice="",
        incident=StopClosure(stop=query.a_stop, start=0, end=1),
    )
    stats = SearchStats()
    try:
        offers, window = route(
            table,
            paths,
            scenario,
            limit=query.limit,
            budget=Budget(deadline_s=DEADLINE_S),
            stats=stats,
        )
    except SearchIncomplete as exc:
        return RouteAnswer(
            network=network,
            status="search_incomplete",
            work=stats.work,
            detail=str(exc),
        )
    return RouteAnswer(
        network=network,
        status="feasible" if offers else "infeasible",
        offers=tuple(offers),
        kept_trips=window.kept_trips,
        work=stats.work,
    )


@router.post("/v1/route", response_model=RouteAnswer)
async def route_endpoint(query: RouteQuery, request: Request) -> RouteAnswer | JSONResponse:
    network = get_settings().network
    cache = request.app.state.__dict__.setdefault("timetables", {})
    if network not in cache:
        cache[network] = await asyncio.to_thread(load, network)
    table, paths = cache[network]
    known = set(table.stop_ids)
    missing = [s for s in (query.a_stop, query.b_stop, query.destination) if s not in known]
    if missing:
        return problem(
            request, 422, "Unknown stop", f"The {network} network has no stop {missing[0]}."
        )
    day = load_scenario().service_date
    return await asyncio.to_thread(solve, table, paths, query, day, network)
