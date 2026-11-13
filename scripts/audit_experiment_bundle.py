"""Verify a completed vNext intake run against its benchmark and manifest."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from experiments.vnext_cases import ROOT, read
from experiments.vnext_runner import Result


def audit(directory: Path, split: str, benchmark: Path = ROOT) -> int:
    manifest = json.loads((directory / f"{split}-manifest.json").read_text())
    artifacts = {f"{split}.md", f"{split}.jsonl", f"{split}-conditions.json"}
    if split == "dev":
        artifacts.add("performance.json")
    if set(manifest["sha256"]) != artifacts:
        raise ValueError("Unexpected bundle contents in the manifest.")
    for name in sorted(artifacts):
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != manifest["sha256"][name]
        ):
            raise ValueError(f"Hash mismatch for {name}.")
    conditions = json.loads((directory / f"{split}-conditions.json").read_text())
    data = hashlib.sha256((benchmark / f"{split}.jsonl").read_bytes()).hexdigest()
    if conditions["split"] != split or data != conditions["data"]:
        raise ValueError("Benchmark provenance mismatch.")
    cases = {case.id: case for case in read(benchmark, split)}
    groups: dict[str, Counter[str]] = {}
    for case in cases.values():
        groups.setdefault(case.group, Counter())[case.language] += 1
    if manifest["cases"] != len(cases) or any(
        languages != {"tr": 1, "en": 1} for languages in groups.values()
    ):
        raise ValueError("Invalid benchmark count or bilingual group.")
    rows = [
        Result.model_validate_json(line)
        for line in (directory / f"{split}.jsonl").read_text().splitlines()
    ]
    actual = Counter((row.case, row.arm) for row in rows)
    expected = Counter(
        (case_id, arm) for case_id in cases for arm in conditions["arms"]
    )
    if actual != expected or any(count != 1 for count in actual.values()):
        raise ValueError("Missing or duplicate case/arm result.")
    for row in rows:
        case = cases[row.case]
        if (row.group, row.family, row.language) != (
            case.group,
            case.family,
            case.language,
        ):
            raise ValueError(f"Case metadata mismatch for {row.case}.")
        if row.model_calls and (
            row.model_digest is None
            or row.model_digest != conditions["models"].get(row.arm)
            or row.request_sha256 is None
        ):
            raise ValueError(f"Missing model provenance for {row.case}/{row.arm}.")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--split", choices=("dev", "calibration", "locked", "holdout"), required=True
    )
    parser.add_argument("--benchmark", type=Path, default=ROOT)
    args = parser.parse_args()
    print(f"Verified {audit(args.directory, args.split, args.benchmark)} result rows.")


if __name__ == "__main__":
    main()
