"""Freeze the authored synthetic bilingual holdout before running predictions."""

import argparse
import hashlib
import json
from pathlib import Path

from trl.domain import StopClosure, TripCancellation, TripDelay
from trl.gtfs import load_schedule
from trl.scenarios import load_scenario

from experiments.vnext_cases import Case, reference

ROOT = Path("data/scenarios/review-v2")


def freeze(source: Path, output: Path) -> int:
    schedule, scenario = load_schedule(), load_scenario()
    groups = json.loads(source.read_text())
    cases: list[Case] = []
    for group in groups:
        name, kind, tr, en = group[:4]
        match kind:
            case "closure" | "paraphrase" | "unsupported_phrase":
                stop, start, end = group[4:]
                incident = StopClosure(stop=stop, start=start, end=end)
            case "cancellation":
                incident = TripCancellation(
                    trip=group[4], service_date=scenario.service_date
                )
            case "delay":
                incident = TripDelay(
                    trip=group[4], service_date=scenario.service_date, seconds=group[5]
                )
            case "negation" | "timezone" | "wrong_date":
                incident = None
            case _:
                raise ValueError(f"Unknown holdout case family {kind}.")
        action = "apply" if incident else "abstain"
        turkish = Case(
            id=f"{name}-tr",
            group=name,
            family=kind,
            language="tr",
            notice=tr,
            incident=incident,
            initial_action=action,
            expected_plan_status="abstained",
        )
        status = reference(schedule, turkish)
        cases.extend(
            (
                turkish.model_copy(update={"expected_plan_status": status}),
                turkish.model_copy(
                    update={
                        "id": f"{name}-en",
                        "language": "en",
                        "notice": en,
                        "expected_plan_status": status,
                    }
                ),
            )
        )
    if len({case.id for case in cases}) != len(cases):
        raise ValueError("Duplicate holdout group.")
    output.mkdir(parents=True, exist_ok=True)
    payload = "".join(case.model_dump_json() + "\n" for case in cases).encode()
    with (output / "holdout.jsonl").open("xb") as handle:
        handle.write(payload)
    with (output / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump({"holdout": hashlib.sha256(payload).hexdigest()}, handle, indent=2)
        handle.write("\n")
    return len(cases)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "cases.json")
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    print(f"Froze {freeze(options.source, options.output)} synthetic notices.")
