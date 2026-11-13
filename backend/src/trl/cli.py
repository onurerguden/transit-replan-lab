"""Inspect timetable-backed plans and maintain the run database from a terminal."""

import argparse
import json
import sys
from pathlib import Path

from trl import dbtools
from trl.disruptions import Overlay
from trl.gtfs import load_schedule
from trl.migrations import migrate
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="trl")
    subcommands = parser.add_subparsers(dest="command", required=True)
    route = subcommands.add_parser("route", help="compare initial and disrupted itinerary pairs")
    route.add_argument("--scenario", choices=("demo", "infeasible"), default="demo")
    database = subcommands.add_parser("db", help="maintain the run database")
    database.add_argument("--db", type=Path, default=None, help="defaults to TRL_DB")
    actions = database.add_subparsers(dest="action", required=True)
    actions.add_parser("migrate", help="apply pending schema migrations")
    actions.add_parser("check", help="verify integrity and run invariants")
    save = actions.add_parser("backup", help="write a consistent copy with a checksum manifest")
    save.add_argument("target", type=Path)
    load = actions.add_parser("restore", help="replace the database from a verified backup")
    load.add_argument("source", type=Path)
    trim = actions.add_parser("prune", help="delete settled runs past a retention period")
    trim.add_argument("--older-than-days", type=float, required=True)
    args = parser.parse_args()
    if args.command == "db":
        sys.exit(run_database(args))
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


def run_database(args: argparse.Namespace) -> int:
    path: Path = args.db or get_settings().database
    match args.action:
        case "migrate":
            print(json.dumps({"applied": migrate(path)}))
        case "check":
            problems = dbtools.invariants(path)
            for item in problems:
                print(f"{item.run_id or '-'}: {item.message}", file=sys.stderr)
            print(json.dumps({"problems": len(problems)}))
            return 1 if problems else 0
        case "backup":
            print(dbtools.backup(path, args.target))
        case "restore":
            print(json.dumps({"applied": dbtools.restore(args.source, path)}))
        case "prune":
            print(
                json.dumps({"removed": dbtools.prune(path, older_than_days=args.older_than_days)})
            )
        case _:
            raise SystemExit(f"Unknown database action: {args.action}")
    return 0


if __name__ == "__main__":
    main()
