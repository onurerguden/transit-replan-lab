"""Check local artifacts against the published vNext training record."""

import argparse
import hashlib
import json
from pathlib import Path

from finetune.vnext_data import overlap

RECORD = Path("experiments/results/vnext/training.json")
EXPECTED_LORA = {
    "rank": 8,
    "scale": 16.0,
    "dropout": 0.0,
    "keys": ["self_attn.q_proj", "self_attn.v_proj"],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--config", type=Path, help="MLX adapter_config.json")
    args = parser.parse_args()
    record = json.loads(RECORD.read_text())
    files = {
        "train_sha256": args.corpus / "train.jsonl",
        "validation_sha256": args.corpus / "valid.jsonl",
        "adapter_gguf_sha256": args.export / "operator.gguf",
        "fused_gguf_sha256": args.export / "operator-fused.gguf",
    }
    for key, path in files.items():
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if record[key] != digest:
            raise ValueError(f"Published digest mismatch for {path.name}.")
    exact = overlap(files["train_sha256"], files["validation_sha256"])
    summary: dict[str, object] = {
        "matched_hashes": len(files),
        "exact_overlap": len(exact),
    }
    if args.config:
        config = json.loads(args.config.read_text())
        expected = {
            "fine_tune_type": "lora",
            "iters": record["training_steps"],
            "seed": record["seed"],
            "num_layers": 4,
            "batch_size": 1,
            "grad_checkpoint": True,
            "lora_parameters": EXPECTED_LORA,
        }
        for key, value in expected.items():
            if config.get(key) != value:
                raise ValueError(f"Training configuration mismatch for {key}.")
        summary["training_config"] = expected
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
