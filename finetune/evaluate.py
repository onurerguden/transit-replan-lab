"""Compare base and adapter using the same local MLX runtime and greedy decoding."""

import argparse
import gc
import hashlib
import json
from pathlib import Path
from time import perf_counter

import mlx.core as mx
from mlx_lm import generate, load

MODEL_REVISION = "0e7ffd5c629ef7719d4cbc04069232580bfa9d9c"


def canonical(text: str) -> dict[str, object] | None:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    fields = {
        "stop_closure": {"stop", "start", "end"},
        "trip_cancellation": {"trip"},
        "trip_delay": {"trip", "minutes"},
        "clarify": set(),
    }
    kind = value.get("kind")
    if not isinstance(kind, str) or kind not in fields:
        return None
    allowed = {"kind", "stop", "start", "end", "trip", "minutes"}
    if not set(value) <= allowed:
        return None
    keys = {key for key, item in value.items() if item is not None}
    if keys != {"kind", *fields[kind]}:
        return None
    for field in fields[kind]:
        if field == "minutes":
            if type(value[field]) is not int:
                return None
        elif not isinstance(value[field], str):
            return None
    return {key: value[key] for key in ("kind", *sorted(fields[kind]))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, default=Path(".local/finetune/adapter"))
    parser.add_argument("--data", type=Path, default=Path(".local/finetune/data"))
    parser.add_argument("--split", choices=("valid", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.split == "test":
        decision = args.output.parent / "decision.json"
        if not decision.is_file():
            raise SystemExit(
                "Record the development adoption decision before held-out evaluation."
            )
    raw = (args.data / f"{args.split}.jsonl").read_bytes()
    expected_hash = json.loads((args.data / "manifest.json").read_text())[args.split][
        "sha256"
    ]
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise SystemExit("Dataset checksum mismatch.")
    rows = [json.loads(line) for line in raw.splitlines()]
    adapter_hash = hashlib.sha256(
        (args.adapter / "adapters.safetensors").read_bytes()
    ).hexdigest()
    condition = {
        "split": args.split,
        "sha256": expected_hash,
        "model_revision": MODEL_REVISION,
        "adapter_sha256": adapter_hash,
        "max_tokens": 100,
    }
    results = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.is_file():
        previous = json.loads(args.output.read_text())
        if any(previous.get(key) != value for key, value in condition.items()):
            raise SystemExit(
                "Existing scores belong to a different evaluation condition."
            )
        results = previous["scores"]
    models = (("base", None), ("adapter", str(args.adapter)))
    for name, adapter in models[len(results) :]:
        model, tokenizer = load(str(args.model), adapter_path=adapter)
        mx.reset_peak_memory()
        started = perf_counter()
        scores = []
        for index, row in enumerate(rows, start=1):
            messages = row["messages"]
            prompt = tokenizer.apply_chat_template(
                messages[:-1],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            reply = generate(
                model, tokenizer, prompt=prompt, max_tokens=100, verbose=False
            )
            expected = canonical(messages[-1]["content"])
            prediction = canonical(reply)
            scores.append(
                {
                    "case": row["id"],
                    "family": row["family"],
                    "language": row["language"],
                    "expected": expected,
                    "prediction": prediction,
                    "schema_valid": prediction is not None,
                    "exact": prediction == expected,
                }
            )
            if index % 10 == 0:
                print(f"{args.split} {name} {index}/{len(rows)}", flush=True)
        results.append(
            {
                "model": name,
                "rows": scores,
                "seconds": round(perf_counter() - started, 2),
                "peak_gb": round(mx.get_peak_memory() / 1e9, 3),
                "exact": sum(score["exact"] for score in scores),
                "clarified": sum(
                    score["exact"] and score["expected"]["kind"] == "clarify"
                    for score in scores
                ),
                "schema_valid": sum(score["schema_valid"] for score in scores),
            }
        )
        del model, tokenizer
        gc.collect()
        mx.clear_cache()
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    **condition,
                    "scores": results,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )
        temporary.replace(args.output)


if __name__ == "__main__":
    main()
