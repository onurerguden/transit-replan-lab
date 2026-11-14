# Train and validate the Operator adapter

The adaptation changes only incident extraction. The deterministic route engine, two-vote requirement, and timetable verifier stay in the application. Review the [data card](DATA_CARD.md) before interpreting exact-match results.

The revised vNext corpus can be generated and audited without training.
The audit script also checks the older artifacts against their published hashes.

```sh
uv run --locked --project backend python -m finetune.vnext_data
uv run --locked --project backend python -m scripts.audit_training \
  --corpus .local/vnext-training --export .local/vnext-export \
  --config .local/vnext-adapter/adapter_config.json
```

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

The exporter transposes MLX LoRA tensors to PEFT layout and writes a GGUF adapter using llama.cpp. The base-model metadata is needed for conversion. Ollama 0.40.16 rejects standalone adapters, so fuse the exported tensors into the pinned Ollama text model before creating the local tag.

```sh
git clone https://github.com/ggml-org/llama.cpp.git .local/mlx/llama.cpp
git -C .local/mlx/llama.cpp checkout cb44fdb1892eebca072e0949875a60c11245a8bb
mkdir -p .local/mlx/qwen35-hf-config
curl -fsSL \
  https://huggingface.co/Qwen/Qwen3.5-4B/resolve/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json \
  -o .local/mlx/qwen35-hf-config/config.json
.local/mlx/venv/bin/python -m finetune.export_adapter \
  --base-config .local/mlx/qwen35-hf-config --llama-cpp .local/mlx/llama.cpp
cmake -S .local/mlx/llama.cpp -B .local/mlx/llama-build \
  -DGGML_METAL=OFF -DGGML_BLAS=OFF -DLLAMA_CURL=OFF \
  -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_SERVER=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
  -DLLAMA_BUILD_TOOLS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build .local/mlx/llama-build --target llama-export-lora --parallel
ollama pull qwen3.5:4b-q4_K_M
python3.12 -m finetune.fuse --models "${OLLAMA_MODELS:-$HOME/.ollama/models}" \
  --fuser .local/mlx/llama-build/bin/llama-export-lora
ollama create trl-operator:adapter -f .local/finetune/export/Modelfile
uv run --locked --project backend python -m finetune.routes --adapter trl-operator:adapter
```

The route runner checks the four declared cases against the reference incident and independent timetable verifier. Ollama must be running for the import and route run. A transportable adapter can still miss the adoption threshold.

References [MLX-LM fine-tuning](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md) · [MLX base snapshot](https://huggingface.co/mlx-community/Qwen3.5-4B-4bit) · [Original Qwen weights and license](https://huggingface.co/Qwen/Qwen3.5-4B) · [llama.cpp adapter converter](https://github.com/ggml-org/llama.cpp/blob/master/convert_lora_to_gguf.py).

The MLX comparison tests strict JSON schema compliance with unconstrained generation. In one development example, the base model correctly asked for the closure times in prose under a `clarify` key, which failed the required schema. The result combines extraction and formatting behavior. The main experiment uses Ollama structured outputs and measures a different condition.

## Measured outcome

The [results](results/REPORT.md) report both MLX evaluation partitions and the Ollama route slice. The initial fused import lacked Qwen's renderer and parser and returned clarification for all four cases. The final recipe preserves these settings. It matched two of four reference outcomes, so the candidate was not adopted for the simulator. The unadapted local Ollama Operator remains the inference default.

## Adapter v3 (TRL-Bench v3.1)

```sh
uv run --locked --project backend python -m finetune.v31_data --output .local/finetune-v31
.local/mlx/venv/bin/python -m mlx_lm lora --config finetune/v31-c1.yml --model .local/mlx/qwen35-4b
```

Stop Ollama first. The three published adapters (seeds 42 to 44) are in `results/v31` with their
losses and checksums. To use one, export and fuse it as above with `--adapter results/v31/adapter-s42`,
then `ollama create` a tag and set `TRL_OPERATOR_MODEL` to it. Evaluate any Ollama model on the dev hard
slice with `python -m finetune.v3_evaluate --model TAG --split dev --hard --workers 4`, start Ollama with
`OLLAMA_NUM_PARALLEL=4`, and score the replies with `python -m experiments.bench_v31 run`. The
[results](../experiments/results/v2_1/REPORT.md) and [ADR 0017](../docs/adr/0017-operator-adapter-v3.md) report the comparison.
