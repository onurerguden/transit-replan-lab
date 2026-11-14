"""Measure meeting queries on the full network: cold start, warm latency and concurrency.

Raw rows go to JSONL so every summary can be recomputed. Wall time depends on the machine, so
the report also lists the deterministic work units of each query.
"""

import argparse
import json
import os
import platform
import random
import resource
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
from trl.disruptions import Overlay
from trl.domain import Constraint, Scenario, StopClosure
from trl.gtfs import DATA_ROOT
from trl.routing import Budget, SearchIncomplete, SearchStats
from trl.timetable.compact import CompactTimetable, get_timetable
from trl.timetable.footpaths import Footpaths, generate
from trl.timetable.query import route
from trl.verify import check_plan

DAY = date(2026, 10, 21)
Overlay0 = Overlay.compile(())
ROOT = DATA_ROOT / "gtfs"
CACHE = Path(".local/cache/timetable")
OPTIONS = {"fast": False}
_STATE: dict[str, tuple[CompactTimetable, Footpaths]] = {}


def state() -> tuple[CompactTimetable, Footpaths]:
    if "loaded" not in _STATE:
        table = get_timetable(ROOT, CACHE, "full")
        documented = {
            (item["origin"], item["destination"]): item["duration"]
            for item in json.loads((ROOT / "transfers.json").read_text())
        }
        paths = generate(
            list(table.stop_ids),
            table.stop_lon.tolist(),
            table.stop_lat.tolist(),
            documented=documented,
        )
        _STATE["loaded"] = (table, paths)
    return _STATE["loaded"]


def distance(table: CompactTimetable, served: np.ndarray, target: int) -> np.ndarray:  # type: ignore[type-arg]
    dx = (table.stop_lon[served] - table.stop_lon[target]) * np.cos(
        np.radians(table.stop_lat[target])
    )
    dy = table.stop_lat[served] - table.stop_lat[target]
    return dx * dx + dy * dy


def scenarios(count: int, seed: int) -> list[Scenario]:
    table, _ = state()
    served = np.unique(table.st_stop)
    rng = random.Random(seed)
    result: list[Scenario] = []
    while len(result) < count:
        d = int(served[rng.randrange(served.size)])
        # Riders start within a few kilometres of the destination so meetings can be feasible.
        near = served[np.argsort(distance(table, served, d))[:300]]
        a, b = (int(near[rng.randrange(near.size)]) for _ in range(2))
        a, b, d = (table.stop_ids[i] for i in (a, b, d))
        if len({a, b, d}) < 3:
            continue
        ready = rng.randrange(7 * 3600, 19 * 3600, 60)
        result.append(
            Scenario(
                id=f"bench-{seed}-{len(result)}",
                service_date=DAY,
                a=Constraint(stop=a, ready=ready, wait_limit=600),
                b=Constraint(
                    stop=b, ready=ready + rng.randrange(0, 600, 60), wait_limit=600
                ),
                destinations=(d,),
                meeting_start=ready,
                meeting_end=ready + 7200,
                notice="",
                incident=StopClosure(stop=a, start=0, end=1),
            )
        )
    return result


def run_one(query: Scenario) -> dict[str, object]:
    table, paths = state()
    stats = SearchStats()
    started = time.perf_counter()
    try:
        offers, window = route(
            table,
            paths,
            query,
            budget=Budget(max_work=2_000_000, deadline_s=30),
            stats=stats,
            fast=OPTIONS["fast"] or os.environ.get("TRL_BENCH_FAST") == "1",
        )
        status = "feasible" if offers else "infeasible"
        invalid = sum(
            check_plan(window.schedule, query, offer, Overlay0) is not None
            for offer in offers
        )
        kept = window.kept_trips
    except SearchIncomplete as exc:
        status, invalid, kept = "incomplete", 0, -1
        stats.work = stats.work or 0
        del exc
    return {
        "id": query.id,
        "status": status,
        "seconds": round(time.perf_counter() - started, 4),
        "work": stats.work,
        "labels": stats.labels,
        "kept_trips": kept,
        "invalid_offers": invalid,
    }


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    seconds = [float(row["seconds"]) for row in rows]  # pyright: ignore[reportArgumentType]
    statuses = [str(row["status"]) for row in rows]
    return {
        "queries": len(rows),
        "feasible": statuses.count("feasible"),
        "infeasible": statuses.count("infeasible"),
        "incomplete": statuses.count("incomplete"),
        "invalid_offers": sum(int(row["invalid_offers"]) for row in rows),  # pyright: ignore[reportArgumentType]
        "p50_s": round(statistics.median(seconds), 3),
        "p95_s": round(percentile(seconds, 0.95), 3),
        "max_s": round(max(seconds), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast", action="store_true", help="dominate across arrival times"
    )
    parser.add_argument("--queries", type=int, default=60)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--workers", type=int, nargs="*", default=[1, 4])
    parser.add_argument(
        "--output", type=Path, default=Path("experiments/results/v2/perf")
    )
    args = parser.parse_args()
    OPTIONS["fast"] = args.fast
    if args.fast:
        os.environ["TRL_BENCH_FAST"] = "1"  # worker processes read it
    args.output.mkdir(parents=True, exist_ok=True)
    cold_started = time.perf_counter()
    state()
    cold = time.perf_counter() - cold_started
    queries = scenarios(args.queries, seed=2026)
    runs: list[dict[str, object]] = []
    report: dict[str, object] = {
        "host": platform.platform(),
        "python": sys.version.split()[0],
        "cold_start_s": round(cold, 3),
        "peak_rss_mb_after_load": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1
        ),
        "runs": runs,
    }
    with (args.output / "raw.jsonl").open("w") as raw:
        for repeat in range(args.repeats):
            for workers in args.workers:
                started = time.perf_counter()
                if workers == 1:
                    rows = [run_one(query) for query in queries]
                else:
                    with ProcessPoolExecutor(workers) as pool:
                        rows = list(pool.map(run_one, queries))
                wall = time.perf_counter() - started
                for row in rows:
                    raw.write(
                        json.dumps({"repeat": repeat, "workers": workers, **row}) + "\n"
                    )
                summary = {
                    "repeat": repeat,
                    "workers": workers,
                    "wall_s": round(wall, 2),
                    **summarize(rows),
                }
                summary["throughput_qps"] = round(len(rows) / wall, 2)
                runs.append(summary)
                print(json.dumps(summary))
    report["peak_rss_mb_final"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1
    )
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
