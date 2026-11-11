"""Merge the GGUF Operator adapter into local text weights for Ollama."""

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True, help="Ollama model cache")
    parser.add_argument(
        "--fuser", type=Path, required=True, help="llama-export-lora executable"
    )
    parser.add_argument(
        "--directory", type=Path, default=Path(".local/finetune/export")
    )
    args = parser.parse_args()
    model = args.models / "manifests/registry.ollama.ai/library/qwen3.5/4b-q4_K_M"
    metadata = json.loads(model.read_text())
    layers = [
        layer
        for layer in metadata["layers"]
        if layer["mediaType"] == "application/vnd.ollama.image.model"
    ]
    if len(layers) != 1:
        raise SystemExit(
            "Expected one GGUF text-weight layer in the pinned Ollama model."
        )
    base = args.models / "blobs" / layers[0]["digest"].replace(":", "-")
    adapter = args.directory / "operator.gguf"
    output = args.directory / "operator-fused.gguf"
    subprocess.run(
        [
            str(args.fuser.resolve()),
            "-m",
            str(base.resolve()),
            "--lora",
            str(adapter.resolve()),
            "-o",
            str(output.resolve()),
        ],
        check=True,
    )
    (args.directory / "Modelfile").write_text(
        f'FROM "{output.resolve()}"\n'
        "RENDERER qwen3.5\n"
        "PARSER qwen3.5\n"
        "PARAMETER top_p 0.95\n"
        "PARAMETER presence_penalty 1.5\n"
        "PARAMETER top_k 20\n"
        "PARAMETER num_ctx 4096\n"
    )


if __name__ == "__main__":
    main()
