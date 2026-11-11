"""Render the measured adaptation decision and route transfer checks."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def report(source: Path) -> str:
    valid = json.loads((source / "valid.json").read_text())
    held = json.loads((source / "test.json").read_text())
    decision = json.loads((source / "decision.json").read_text())
    routes = json.loads((source / "routes.json").read_text())
    training = json.loads((source / "training.json").read_text())
    if training["steps"] != 360 or len(routes) != 4:
        raise ValueError("The full training run and all route checks must be complete.")
    duration = training["elapsed_seconds"]
    checksum = training["gguf_sha256"]
    rows = [
        "# Operator LoRA results",
        "",
        "Apple M1 Pro, 16 GB · MLX-LM 0.32.0 · Qwen3.5 4B 4-bit · seed 42",
        "",
        f"The 25-step pilot and 360-step training run completed. Full training took {duration} s.",
        f"The GGUF adapter SHA-256 is `{checksum}`.",
        "",
        "| Partition | Model | Exact match | Correct clarification | Schema-valid |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for label, evaluation in (("Development", valid), ("Held-out", held)):
        for item in evaluation["scores"]:
            total = len(item["rows"])
            clarify = sum(row["expected"]["kind"] == "clarify" for row in item["rows"])
            rows.append(
                f"| {label} | {item['model']} | {item['exact']}/{total} | "
                f"{item['clarified']}/{clarify} | {item['schema_valid']}/{total} |"
            )
    safe_routes = all(
        row["baseline_status"] == row["status"]
        and row["incident_correct"]
        and not row["hard_violation"]
        for row in routes
    )
    eligible = decision["eligible"] and safe_routes
    rows += [
        "",
        (
            f"The development exact-match change was **{decision['exact_delta_pp']:+.2f} points** "
            f"with **{decision['clarification_delta']:+d} correct clarifications**. "
            f"The adapter was **{'accepted as an opt-in candidate' if eligible else 'not adopted'}**."
        ),
        "",
        "## Ollama route slice",
        "",
        "| Case | Base outcome | Adapted outcome | Exact incident | Hard violation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in routes:
        rows.append(
            f"| `{row['case']}` | {row['baseline_status']} | {row['status']} | "
            f"{row['incident_correct']} | {row['hard_violation']} |"
        )
    failures = [
        row
        for item in held["scores"]
        if item["model"] == "adapter"
        for row in item["rows"]
        if not row["exact"]
    ]
    if failures:
        example = failures[0]
        rows += [
            "",
            "## Error example",
            "",
            (
                f"`{example['case']}` expected `{json.dumps(example['expected'], ensure_ascii=False)}` "
                f"and produced `{json.dumps(example['prediction'], ensure_ascii=False)}`."
            ),
        ]
    return "\n".join(rows) + "\n"


def capture_training(source: Path) -> None:
    pattern = r"\x1b\[[0-9;]*m"
    pilot = re.sub(pattern, "", (source / "pilot.log").read_text())
    text = re.sub(pattern, "", (source / "train.log").read_text())
    if "25/25" not in pilot or "360/360" not in text:
        raise ValueError("Expected completed pilot and training logs.")
    duration = next(
        float(line.split()[1]) for line in text.splitlines() if line.startswith("real ")
    )
    checksum = hashlib.sha256(
        (source / "export" / "operator.gguf").read_bytes()
    ).hexdigest()
    result = {
        "device": "Apple M1 Pro, 16 GB",
        "mlx_lm": "0.32.0",
        "pilot_steps": 25,
        "steps": 360,
        "elapsed_seconds": duration,
        "gguf_sha256": checksum,
    }
    (source / "training.json").write_text(json.dumps(result, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--capture-training", action="store_true")
    args = parser.parse_args()
    if args.capture_training:
        capture_training(args.source)
    args.target.write_text(report(args.source))


if __name__ == "__main__":
    main()
