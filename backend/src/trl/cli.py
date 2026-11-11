"""Inspect timetable-backed plans from a terminal."""

import argparse
import json

from trl.disruptions import Overlay
from trl.gtfs import load_schedule
from trl.routing import find_offers
from trl.scenarios import load_scenario


def main() -> None:
    parser = argparse.ArgumentParser(prog="trl")
    subcommands = parser.add_subparsers(dest="command", required=True)
    route = subcommands.add_parser("route", help="compare initial and disrupted itinerary pairs")
    route.add_argument("--scenario", choices=("demo", "infeasible"), default="demo")
    args = parser.parse_args()
    scenario = load_scenario(args.scenario)
    schedule = load_schedule()
    initial = find_offers(schedule, scenario, limit=1)
    replanned = find_offers(schedule, scenario, 1, Overlay.compile((scenario.incident,)))
    print(
        json.dumps(
            {
                "initial": [offer.model_dump(mode="json") for offer in initial],
                "candidates": [offer.model_dump(mode="json") for offer in replanned],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
