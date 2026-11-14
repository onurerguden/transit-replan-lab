"""Export a blind annotation packet from a TRL-Bench v3 split.

The packet holds anonymous report ids and texts. Annotators decide the action and the event
themselves. The key that maps ids back to benchmark ids and gold labels stays private and is
never written next to the packet. Two annotators fill the same file independently.
"""

import argparse
import csv
import json
import random
from pathlib import Path

from experiments.bench_v3.generate import read

FIELDS = [
    "id",
    "language",
    "text",
    "action",
    "event",
    "stop_or_trip",
    "start",
    "end",
    "note",
]
ACTIONS = "apply (one clear event) | ask (event but a detail is missing) | abstain (no usable event)"
EVENTS = "stop_closure | trip_delay | trip_cancellation | none"


def export(split: Path, count: int, seed: int, output: Path, key: Path) -> None:
    reports = read(split)
    groups = sorted({report.group for report in reports})
    random.Random(seed).shuffle(groups)
    chosen = set(groups[: count // 2])
    rows = [report for report in reports if report.group in chosen]
    random.Random(seed + 1).shuffle(rows)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "packet.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS)
        writer.writeheader()
        for number, report in enumerate(rows, start=1):
            writer.writerow(
                {"id": f"r{number:04d}", "language": report.lang, "text": report.text}
            )
    (output / "INSTRUCTIONS.md").write_text(
        "# Annotation instructions\n\n"
        "Read each report as a rider would. Do not look anything up. Fill these columns "
        "without discussing with the other annotator.\n\n"
        f"- `action`: {ACTIONS}\n- `event`: {EVENTS}\n"
        "- `stop_or_trip`: the stop name or the trip identifier the report names, as written\n"
        "- `start`, `end`: service times as HH:MM, only if the report states them\n"
        "- `note`: anything unclear, and whether the report reads naturally\n\n"
        "Use `abstain` when the report is negated, hedged, about another day or another time "
        "zone, or names no disruption.\n",
        encoding="utf-8",
    )
    key.parent.mkdir(parents=True, exist_ok=True)
    key.write_text(
        json.dumps(
            {f"r{n:04d}": report.id for n, report in enumerate(rows, start=1)},
            indent=1,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, default=Path("data/bench/v3/test.jsonl"))
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261114)
    parser.add_argument("--output", type=Path, default=Path(".local/review-packet"))
    parser.add_argument("--key", type=Path, default=Path(".local/review-key/key.json"))
    args = parser.parse_args()
    export(args.split, args.count, args.seed, args.output, args.key)


if __name__ == "__main__":
    main()
