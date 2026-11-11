"""Convert MLX attention LoRA tensors to PEFT, then to a GGUF adapter."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import mlx.core as mx
import numpy as np
from safetensors.numpy import save_file

BASE_ID = "Qwen/Qwen3.5-4B"


def peft(adapter: Path, output: Path) -> None:
    config = json.loads((adapter / "adapter_config.json").read_text())
    options = config["lora_parameters"]
    rank = int(options["rank"])
    weights = mx.load(str(adapter / "adapters.safetensors"))
    mapped: dict[str, np.ndarray] = {}
    for name, tensor in weights.items():
        root, _, suffix = name.rpartition(".")
        if root.startswith("language_model.model."):
            root = "model.language_model." + root.removeprefix("language_model.model.")
        if not root.startswith("model.language_model.layers.") or not root.endswith(
            (".self_attn.q_proj", ".self_attn.v_proj")
        ):
            raise ValueError(f"Unexpected adapter module {name}.")
        if suffix not in {"lora_a", "lora_b"} or tensor.ndim != 2:
            raise ValueError(f"Unexpected adapter tensor {name}.")
        key = f"base_model.model.{root}.lora_{suffix[-1].upper()}.weight"
        mapped[key] = np.ascontiguousarray(np.array(tensor.astype(mx.float32)).T)
    if not mapped or len(mapped) != len(weights):
        raise ValueError("Adapter tensor names did not map one to one.")
    output.mkdir(parents=True, exist_ok=True)
    save_file(mapped, output / "adapter_model.safetensors")
    (output / "adapter_config.json").write_text(
        json.dumps(
            {
                "base_model_name_or_path": BASE_ID,
                "peft_type": "LORA",
                "task_type": "CAUSAL_LM",
                "r": rank,
                "lora_alpha": float(options["scale"]) * rank,
                "target_modules": ["q_proj", "v_proj"],
                "bias": "none",
            },
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=Path(".local/finetune/adapter"))
    parser.add_argument("--output", type=Path, default=Path(".local/finetune/export"))
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--llama-cpp", type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    peft(args.adapter, target / "peft")
    converter = args.llama_cpp.resolve()
    gguf = target / "operator.gguf"
    subprocess.run(
        [
            sys.executable,
            str(converter / "convert_lora_to_gguf.py"),
            "--base",
            str(args.base_config.resolve()),
            "--outtype",
            "f16",
            "--outfile",
            str(gguf),
            str(target / "peft"),
        ],
        env={**os.environ, "PYTHONPATH": str(converter / "gguf-py")},
        check=True,
    )


if __name__ == "__main__":
    main()
