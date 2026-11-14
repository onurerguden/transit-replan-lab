"""Measure agreement between two annotators and against the generated gold.

Reads two filled `packet.csv` files and the private key. Prints Cohen's kappa for the action and
the event, lists disagreements for adjudication, and reports how often each annotator matches
the generated label.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from experiments.bench_v3.generate import Report, read


def load(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["id"]: row for row in csv.DictReader(handle)}


def kappa(left: list[str], right: list[str]) -> float:
    n = len(left)
    if n == 0:
        return 0.0
    observed = sum(a == b for a, b in zip(left, right, strict=True)) / n
    counts_left, counts_right = Counter(left), Counter(right)
    expected = sum(counts_left[c] * counts_right[c] for c in counts_left) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def gold_event(report: Report) -> str:
    return str(report.incidents[0]["kind"]) if report.incidents else "none"


def compare(first: Path, second: Path, key: Path, split: Path) -> dict[str, object]:
    a, b = load(first), load(second)
    mapping = json.loads(key.read_text())
    gold = {report.id: report for report in read(split)}
    ids = sorted(set(a) & set(b) & set(mapping))
    result: dict[str, object] = {"reports": len(ids)}
    for field in ("action", "event"):
        left = [a[i][field].strip() for i in ids]
        right = [b[i][field].strip() for i in ids]
        result[f"kappa_{field}"] = round(kappa(left, right), 3)
        result[f"disagreements_{field}"] = [
            i for i, x, y in zip(ids, left, right) if x != y
        ]
    for name, rows in (("first", a), ("second", b)):
        result[f"{name}_matches_gold_action"] = sum(
            rows[i]["action"].strip() == gold[mapping[i]].action for i in ids
        )
        result[f"{name}_matches_gold_event"] = sum(
            rows[i]["event"].strip() == gold_event(gold[mapping[i]]) for i in ids
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--key", type=Path, default=Path(".local/review-key/key.json"))
    parser.add_argument("--split", type=Path, default=Path("data/bench/v3/test.jsonl"))
    args = parser.parse_args()
    print(json.dumps(compare(args.first, args.second, args.key, args.split), indent=1))


if __name__ == "__main__":
    main()
