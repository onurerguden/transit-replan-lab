"""Training rows for the Operator adapter, drawn only from the TRL-Bench v3 train split.

The adapter learns to quote the phrase that names the event and to state its kind, and to
return nothing for reports that name no event, deny it or hedge it. Validation rows come from
the first 50 dev groups. The rest of dev is left for the adoption decision.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

from trl.agents import PROMPT_DIR
from trl.vnext import Extraction, ExtractionQuote

from experiments.bench_v3.generate import Report, read

OUT = Path(".local/finetune-v2")
VALID_GROUPS = 50
TRAIN_ROWS = 1800


def grounded(text: str, phrase: str | None) -> str | None:
    if phrase and phrase in text:
        return phrase
    if phrase and (tail := phrase.split()[-1]) in text:
        return tail
    return None


def target(report: Report) -> Extraction | None:
    """The reply a perfect Operator gives for this report, or None if no quote is grounded."""
    if report.action == "abstain" or not report.incidents:
        return Extraction()
    quote = grounded(report.text, report.kind_phrase)
    if quote is None:
        return None
    kind = report.incidents[0]["kind"]
    return Extraction(
        quotes=(
            ExtractionQuote.model_validate(
                {"slot": "kind", "quote": quote, "kind": kind}
            ),
        )
    )


def row(report: Report, prompt: str) -> dict[str, object] | None:
    answer = target(report)
    if answer is None:
        return None
    return {
        "id": report.id,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps({"notice": report.text}, ensure_ascii=False),
            },
            {"role": "assistant", "content": answer.model_dump_json(exclude_none=True)},
        ],
    }


def build(root: Path = OUT) -> dict[str, object]:
    prompt = (PROMPT_DIR / "operator_vnext.md").read_text()
    train = read(Path("data/bench/v3/train.jsonl"))
    dev = read(Path("data/bench/v3/dev.jsonl"))
    rng = random.Random(42)
    rng.shuffle(train)
    rows = [item for report in train if (item := row(report, prompt))][:TRAIN_ROWS]
    valid_ids = {f"dev-{index:05d}" for index in range(VALID_GROUPS)}
    valid = [
        item
        for report in dev
        if report.group in valid_ids and (item := row(report, prompt))
    ]
    root.mkdir(parents=True, exist_ok=True)
    for name, items in (("train", rows), ("valid", valid)):
        (root / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n"
        )
    overlap = {r["messages"][1]["content"] for r in rows} & {  # type: ignore[index]
        r["messages"][1]["content"]
        for r in valid  # type: ignore[index]
    }
    manifest = {
        "train_rows": len(rows),
        "valid_rows": len(valid),
        "exact_overlap": len(overlap),
        "sha256": {
            name: hashlib.sha256((root / f"{name}.jsonl").read_bytes()).hexdigest()
            for name in ("train", "valid")
        },
        "source": "data/bench/v3 train split and dev groups below 50",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    print(json.dumps(build(parser.parse_args().output)))
