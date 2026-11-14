"""Training rows for the Operator adapter, drawn only from the TRL-Bench v3.1 train split.

Rows are deduplicated by wording: reports whose masked text shares most word trigrams with an
earlier report are dropped, so a few thousand template-level variants do not outweigh the
distinct wordings. Validation rows come from the first 50 dev groups. The rest of dev is kept for
choosing a configuration. With `--rag` the user message carries retrieved train examples, and a
training row never retrieves its own template.
"""

import argparse
import hashlib
import json
import random
from pathlib import Path

from trl.agents import PROMPT_DIR

from experiments.bench_v3 import catalogue, overlap
from experiments.bench_v3.audit import mask
from experiments.bench_v31 import generate
from finetune import rag
from finetune.v2_data import target

ROOT = Path("data/bench/v31")
VALID_GROUPS = 50
SPARSE_ROWS = 60
RAG_PROMPT = Path("finetune/prompts/operator_rag.md")


def messages(system: str, user: str, answer: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": answer},
    ]


def build(output: Path, rows: int, use_rag: int, seed: int = 42) -> dict[str, object]:
    stops, _, _ = catalogue.load()
    names = list(stops.values())
    train = generate.read(ROOT / "train.jsonl")
    dev = generate.read(ROOT / "dev.jsonl")
    random.Random(seed).shuffle(train)
    dropped = overlap.near_duplicates(
        [overlap.shingles(mask(r.text, names)) for r in train], 0.8
    )
    # Delay, cancellation and no-event reports have one wording per split, so deduplication would
    # leave a handful. Keep a fixed share of them so the adapter still sees the trip kinds.
    sparse = {"delay", "cancellation", "unrelated"}
    seen: dict[str, int] = {}
    kept = []
    for number, report in enumerate(train):
        if report.family in sparse:
            seen[report.family] = seen.get(report.family, 0) + 1
            if seen[report.family] <= SPARSE_ROWS:
                kept.append(report)
        elif number not in dropped:
            kept.append(report)
    index = rag.build(ROOT / "train.jsonl") if use_rag else None
    system = (RAG_PROMPT if use_rag else PROMPT_DIR / "operator_vnext.md").read_text()

    def row(report: generate.Report) -> dict[str, object] | None:
        answer = target(report)
        if answer is None:
            return None
        user = (
            rag.view(index, report.text, use_rag)
            if index
            else json.dumps({"notice": report.text}, ensure_ascii=False)
        )
        reply = answer.model_dump_json(exclude_none=True)
        return {"id": report.id, "messages": messages(system, user, reply)}

    train_rows = [item for r in kept if (item := row(r))][:rows]
    valid_ids = {f"dev-{i:05d}" for i in range(VALID_GROUPS)}
    valid_rows = [item for r in dev if r.group in valid_ids and (item := row(r))]
    output.mkdir(parents=True, exist_ok=True)
    for name, items in (("train", train_rows), ("valid", valid_rows)):
        (output / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(i, ensure_ascii=False) for i in items) + "\n"
        )
    families: dict[str, int] = {}
    by_id = {r.id: r for r in train}
    for item in train_rows:
        family = by_id[str(item["id"])].family
        families[family] = families.get(family, 0) + 1
    manifest = {
        "train_rows": len(train_rows),
        "valid_rows": len(valid_rows),
        "near_duplicates_dropped": len(dropped),
        "families": dict(sorted(families.items())),
        "rag_examples": use_rag,
        "sha256": {
            n: hashlib.sha256((output / f"{n}.jsonl").read_bytes()).hexdigest()
            for n in ("train", "valid")
        },
        "source": "data/bench/v31 train split and dev groups below 50",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/finetune-v31"))
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--rag", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.rows, args.rag), indent=1))
