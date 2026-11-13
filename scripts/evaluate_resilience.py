"""Measure the early and resilient offer on each frozen, feasible incident group."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from trl.disruptions import Overlay
from trl.gtfs import load_schedule
from trl.robustness import compare
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.verify import check_plan

from experiments.vnext_cases import ROOT, read


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=("dev", "locked"), default="dev")
    parser.add_argument("--benchmark", type=Path, default=ROOT)
    parser.add_argument("--margin-aware", action="store_true")
    options = parser.parse_args()
    schedule = load_schedule()
    rows: list[dict[str, int | str | float | None]] = []
    for case in read(options.benchmark, options.split):
        if (
            case.language != "en"
            or case.expected_plan_status != "feasible"
            or case.incident is None
        ):
            continue
        scenario = load_scenario("infeasible" if case.tight_window else "demo")
        overlay = Overlay.compile((case.incident,))
        initial = next(iter(find_offers(schedule, scenario, limit=1)), None)
        start = perf_counter()
        candidates = tuple(
            find_offers(
                schedule,
                scenario,
                1,
                overlay,
                diverse=True,
                initial=initial,
                margin_aware=options.margin_aware,
            )
        )
        offers, evidence = compare(
            schedule, scenario, candidates, overlay, initial, "earliest"
        )
        assert all(
            check_plan(schedule, scenario, offer, overlay) is None for offer in offers
        )
        early, robust = (
            next(
                (offer, record)
                for offer, record in zip(offers, evidence, strict=True)
                if policy in record.policies
            )
            for policy in ("earliest", "robust")
        )
        rows.append(
            {
                "group": case.group,
                "worlds": early[1].total,
                "split": options.split,
                "margin_aware": options.margin_aware,
                "candidates": len(candidates),
                "search_and_compare_ms": round((perf_counter() - start) * 1000, 3),
                "earliest_success": early[1].successful,
                "robust_success": robust[1].successful,
                "later_meeting_s": robust[0].meeting - early[0].meeting,
                "earliest_extra_a_s": early[1].extra_seconds_a,
                "earliest_extra_b_s": early[1].extra_seconds_b,
                "robust_extra_a_s": robust[1].extra_seconds_a,
                "robust_extra_b_s": robust[1].extra_seconds_b,
            }
        )
    with options.output.open("x", encoding="utf-8") as handle:
        handle.writelines(json.dumps(row) + "\n" for row in rows)


if __name__ == "__main__":
    main()
