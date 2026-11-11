"""Summarize paired outcomes from immutable runner rows."""

import argparse
import math
from pathlib import Path
from random import Random
from statistics import mean, median
from typing import Literal

from trl.domain import Record, Status


class Row(Record):
    split: str
    case: str
    family: str
    language: str
    arm: str
    status: Status
    oracle: Literal["feasible", "infeasible", "clarification"]
    incident_correct: bool
    outcome_correct: bool
    success: bool
    hard_violation: bool
    late_s: int | None
    delay_s: int | None
    calls: int
    input_tokens: int
    output_tokens: int
    elapsed_ms: int
    model_digest: str
    gtfs: dict[str, str]
    prompt_version: str
    commit: str
    seed: int
    counteroffers: bool
    error: str | None = None


def rows(path: Path) -> list[Row]:
    return [
        Row.model_validate_json(line) for line in path.read_text().splitlines() if line
    ]


def percentile(data: list[float], q: float) -> float:
    ordered = sorted(data)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)] if ordered else 0


def paired_ci(arm: list[Row], baseline: dict[str, Row]) -> tuple[float, float]:
    differences = [
        float(item.success) - float(baseline[item.case].success)
        for item in arm
        if item.oracle == "feasible" and item.case in baseline
    ]
    if not differences:
        return 0, 0
    rng = Random(2026)
    samples = [
        100 * mean(rng.choices(differences, k=len(differences))) for _ in range(2000)
    ]
    return percentile(samples, 0.025), percentile(samples, 0.975)


def table(data: list[Row], split: str) -> str:
    selected = [row for row in data if row.split == split]
    baseline = {row.case: row for row in selected if row.arm == "rules"}
    head = (
        "| Coordinator | N | Verified and correct | Outcome correct | Clarification | "
        "Hard violations | Median gap | Median recovery delay | Mean calls | Mean tokens | p95 | Δ vs rules, 95% CI |"
    )
    lines = [head, "|" + "|".join([" --- "] * 12) + "|"]
    for name in ("rules", "single", "three", "five", "five-no-counter"):
        arm = [row for row in selected if row.arm == name]
        if not arm:
            continue
        eligible = [row for row in arm if row.oracle == "feasible"]
        clarify = [row for row in arm if row.oracle == "clarification"]
        late = [row.late_s for row in arm if row.late_s is not None]
        recovery = [row.delay_s for row in arm if row.delay_s is not None]
        low, high = paired_ci(arm, baseline)
        lateness = f"{median(late):.0f} s" if late else "—"
        delay = f"{median(recovery):.0f} s" if recovery else "—"
        lines.append(
            f"| {name} | {len(arm)} | {sum(row.success for row in eligible)}/{len(eligible)} "
            f"| {sum(row.outcome_correct for row in arm)}/{len(arm)} "
            f"| {sum(row.status == 'clarification' for row in clarify)}/{len(clarify)} "
            f"| {sum(row.hard_violation for row in arm)} | {lateness} | {delay} "
            f"| {mean(row.calls for row in arm):.2f} "
            f"| {mean(row.input_tokens + row.output_tokens for row in arm):.0f} "
            f"| {percentile([float(row.elapsed_ms) for row in arm], 0.95) / 1000:.2f} s "
            f"| [{low:+.1f}, {high:+.1f}] pp |"
        )
    return "\n".join(lines)


def report(data: list[Row]) -> str:
    sections = ["# Comparative evaluation", ""]
    for split in ("dev", "locked"):
        if not any(row.split == split for row in data):
            continue
        sections += [f"## {split.title()}", "", table(data, split), ""]
    locked = [row for row in data if row.split == "locked"]
    if locked:
        matched = {row.case: row for row in locked if row.arm == "five"}
        ablation = [row for row in locked if row.arm == "five-no-counter"]
        if ablation:
            before = sum(
                matched[row.case].success for row in ablation if row.case in matched
            )
            after = sum(row.success for row in ablation)
            sections += [
                "## Counteroffer ablation",
                "",
                (
                    f"Across {len(ablation)} matched cases, five roles succeeded {before} times "
                    f"with counteroffers and {after} times with a single round."
                ),
                "",
            ]
        sections += ["## Failure examples", ""]
        failures = [row for row in locked if not row.outcome_correct]
        for row in failures[:4]:
            sections.append(
                f"- `{row.case}` / {row.arm} ended with `{row.status}` "
                f"against expected `{row.oracle}`. Incident exact match was "
                f"{'true' if row.incident_correct else 'false'}."
            )
    return "\n".join(sections).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    args.target.write_text(report(rows(args.source)))


if __name__ == "__main__":
    main()
