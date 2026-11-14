# pyright: basic
"""Paired contrasts with cluster-bootstrap intervals, as registered for the Operator comparison.

Reads the per-report rows written by `experiments.bench_v31 run` and prints, for each registered
contrast, the paired difference in accuracy with its 95% two-level cluster interval, the exact
McNemar p value and the Holm-adjusted p value.
"""

import argparse
import json
from pathlib import Path

from experiments.bench_v3 import stats

CONTRASTS = (
    ("adapter", "lexicon"),
    ("adapter", "base"),
    ("adapter", "rag4"),
    ("rag4", "base"),
)


def label(arm: str) -> str:
    return arm.partition("=")[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rows", type=Path)
    parser.add_argument("--draws", type=int, default=10000)
    args = parser.parse_args()
    by_arm: dict[str, dict[str, dict[str, object]]] = {}
    for line in args.rows.read_text().splitlines():
        row = json.loads(line)
        by_arm.setdefault(label(row["arm"]), {})[row["id"]] = row
    results = []
    raw: dict[str, float] = {}
    for left, right in CONTRASTS:
        ids = sorted(set(by_arm[left]) & set(by_arm[right]))
        diff = [
            float(bool(by_arm[left][i]["correct"]))
            - float(bool(by_arm[right][i]["correct"]))
            for i in ids
        ]
        clusters = [str(by_arm[left][i]["cluster"]) for i in ids]
        centre, low, high = stats.cluster_bootstrap(diff, clusters, draws=args.draws)
        only_left = sum(d > 0 for d in diff)
        only_right = sum(d < 0 for d in diff)
        raw[f"{left} - {right}"] = stats.mcnemar_exact(only_left, only_right)
        results.append(
            (left, right, len(ids), centre, low, high, only_left, only_right)
        )
    adjusted = stats.holm(raw)
    print(
        "| Contrast | Reports | Difference | 95% cluster interval | Only left right | Only right right | Holm p |"
    )
    print("| --- | ---: | ---: | --- | ---: | ---: | ---: |")
    for left, right, n, centre, low, high, a, b in results:
        name = f"{left} - {right}"
        print(
            f"| {name} | {n} | {centre * 100:+.1f} pts | [{low * 100:+.1f}, {high * 100:+.1f}] | {a} | {b} | {adjusted[name]:.4f} |"
        )


if __name__ == "__main__":
    main()
