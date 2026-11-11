# Train and validate the Operator adapter

The adaptation changes only incident extraction. The deterministic route engine, two-vote requirement, and timetable verifier stay in the application. Review the [data card](DATA_CARD.md) before interpreting exact-match results.

## Apple silicon setup

The run used MLX-LM 0.32.0 and the community 4-bit Qwen3.5 4B snapshot. Stop the local Ollama process before training or running MLX evaluation.

```sh
make setup
uv venv --python 3.12 .local/mlx/venv
uv pip install --python .local/mlx/venv/bin/python -r finetune/requirements.txt
.local/mlx/venv/bin/hf download mlx-community/Qwen3.5-4B-4bit \
  --revision 0e7ffd5c629ef7719d4cbc04069232580bfa9d9c \
  --local-dir .local/mlx/qwen35-4b
make finetune-data
cmp finetune/manifest.json .local/finetune/data/manifest.json
make finetune-pilot
make finetune
make finetune-eval
```

The pilot uses 25 steps. The full run starts from the original weights and trains 360 steps with batch size 1 and gradient checkpointing. The last four transformer blocks are eligible, with updates restricted to query and value projections in the full-attention block. Both checkpoints use rank 8, scale 16, and a 384-token training window. Compare the two development scores in `.local/finetune/valid.json` and apply the data card threshold before running the held-out evaluation.

```sh
make finetune-eval FINETUNE_SPLIT=test
```

## Export for a local Ollama test

The exporter transposes MLX LoRA tensors to PEFT layout and writes a GGUF adapter using llama.cpp. The base-model metadata is needed for conversion, while the original Ollama model supplies the quantized inference weights.

```sh
git clone https://github.com/ggml-org/llama.cpp.git .local/mlx/llama.cpp
git -C .local/mlx/llama.cpp checkout cb44fdb1892eebca072e0949875a60c11245a8bb
mkdir -p .local/mlx/qwen35-hf-config
curl -fsSL \
  https://huggingface.co/Qwen/Qwen3.5-4B/resolve/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json \
  -o .local/mlx/qwen35-hf-config/config.json
.local/mlx/venv/bin/python -m finetune.export_adapter \
  --base-config .local/mlx/qwen35-hf-config --llama-cpp .local/mlx/llama.cpp
ollama pull qwen3.5:4b-q4_K_M
ollama create trl-operator:adapter -f .local/finetune/export/Modelfile
uv run --locked --project backend python -m finetune.routes --adapter trl-operator:adapter
```

The route runner checks the four declared cases against the reference incident and independent timetable verifier. Ollama must be running for the import and route run. A transportable adapter can still miss the adoption threshold.

References [MLX-LM fine-tuning](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md) · [MLX base snapshot](https://huggingface.co/mlx-community/Qwen3.5-4B-4bit) · [Original Qwen weights and license](https://huggingface.co/Qwen/Qwen3.5-4B) · [llama.cpp adapter converter](https://github.com/ggml-org/llama.cpp/blob/master/convert_lora_to_gguf.py).
