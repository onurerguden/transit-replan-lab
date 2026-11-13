"""Compare question policies on controlled two-field ambiguity in archived GTFS."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from trl.gtfs import load_schedule
from trl.intake import decide, residual
from trl.scenarios import load_scenario
from trl.vnext import Fact, Impact, Slot

from experiments.vnext_runner import Context, code_digest

WINDOWS = ((31800, 36000), (32400, 36000), (33000, 35400), (33600, 36000))
TARGETS = (("tram:7", "tram:8"), ("tram:7", "tram:3"), ("tram:8", "tram:3"))
ARMS = ("fixed", "impact")


def worst_residual(impacts: Sequence[Impact], slot: Slot) -> tuple[int, int]:
    partitions: dict[str | int, list[Impact]] = {}
    for impact in impacts:
        value = next(
            fact.value for fact in impact.hypothesis.facts if fact.slot == slot
        )
        partitions.setdefault(value, []).append(impact)
    return max(residual(group) for group in partitions.values())


def run(output: Path) -> None:
    schedule, scenario = load_schedule(), load_scenario()
    context = Context(schedule)
    rows: list[dict[str, object]] = []
    for window in WINDOWS:
        for targets in TARGETS:
            for tight in (False, True):
                facts = (
                    Fact(slot="kind", value="stop_closure"),
                    Fact(slot="start", value=30240),
                    *(Fact(slot="target", value=target) for target in targets),
                    *(Fact(slot="end", value=end) for end in window),
                )
                outcome: dict[str, object] = {}
                for arm in ARMS:
                    intake = decide(
                        facts,
                        (),
                        schedule,
                        scenario.service_date,
                        context.preview(tight),
                        1,
                        strategy=arm,
                    )
                    if intake.question is None or len(intake.impacts) != 4:
                        raise ValueError(
                            "Expected four hypotheses and one clarification."
                        )
                    slot = intake.question.slot
                    outcome[arm] = {
                        "slot": slot,
                        "residual": worst_residual(intake.impacts, slot),
                    }
                rows.append(
                    {
                        "targets": targets,
                        "end_options": window,
                        "tight": tight,
                        **outcome,
                    }
                )
    with output.open("x", encoding="utf-8") as handle:
        json.dump(
            {"source": code_digest(), "unit": "structured ambiguity", "results": rows},
            handle,
            indent=2,
        )
        handle.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
