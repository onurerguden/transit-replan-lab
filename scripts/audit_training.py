"""Check local artifacts against the published vNext training record."""

import argparse
import hashlib
import json
from pathlib import Path

from finetune.vnext_data import overlap

RECORD = Path("experiments/results/vnext/training.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--export", type=Path, required=True)
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
    print(
        json.dumps(
            {"matched_hashes": len(files), "exact_overlap": len(exact)}, indent=2
        )
    )


if __name__ == "__main__":
    main()
