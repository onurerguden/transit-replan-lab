"""Create a blinded review packet and a separate private arm mapping."""

import argparse
import json
from pathlib import Path
from random import Random

from experiments.vnext_cases import Case
from experiments.vnext_runner import Result


def export(cases_path: Path, results_path: Path, output: Path, seed: int) -> int:
    parsed = [
        Case.model_validate_json(line) for line in cases_path.read_text().splitlines()
    ]
    cases = {case.id: case for case in parsed}
    if len(cases) != len(parsed):
        raise ValueError("Duplicate case identifier.")
    results = [
        Result.model_validate_json(line)
        for line in results_path.read_text().splitlines()
    ]
    arms = sorted({row.arm for row in results})
    expected = {(case_id, arm) for case_id in cases for arm in arms}
    actual = {(row.case, row.arm) for row in results}
    if (
        len(arms) < 2
        or not cases
        or actual != expected
        or len(results) != len(expected)
    ):
        raise ValueError(
            "Provide a complete case-by-arm matrix with at least two arms."
        )
    rng = Random(seed)
    rng.shuffle(arms)
    codes = {arm: f"arm-{number:02d}" for number, arm in enumerate(arms, start=1)}
    rng.shuffle(results)
    output.mkdir(mode=0o700, parents=True)
    with (output / "packet.jsonl").open("x", encoding="utf-8") as packet:
        for row in results:
            case = cases[row.case]
            item = {
                "case": case.id,
                "arm": codes[row.arm],
                "language": case.language,
                "notice": case.notice,
                "reference_answer": case.answer,
                "initial_action": row.initial,
                "terminal": row.terminal,
                "proposed_incident": row.incident.model_dump(mode="json")
                if row.incident
                else None,
            }
            packet.write(json.dumps(item, ensure_ascii=False) + "\n")
    with (output / "arm-key.json").open("x", encoding="utf-8") as key:
        json.dump(
            {"seed": seed, "arms": {code: arm for arm, code in codes.items()}},
            key,
            indent=2,
        )
        key.write("\n")
    return len(results)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(
        f"Exported {export(args.cases, args.results, args.output, args.seed)} blinded rows."
    )


if __name__ == "__main__":
    main()
