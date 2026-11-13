# Operator adapter v2

See [ADR 0016](../../../docs/adr/0016-operator-adapter-v2.md) for the decision and
[`training.json`](training.json) for the run. Replies and scores are in
[`experiments/results/v2/bench-models`](../../../experiments/results/v2/bench-models).

| Arm | Test subset correct | Schema-valid replies | p50 latency |
| --- | ---: | ---: | ---: |
| Rules and phrase list | 322 / 600 (53.7%) | not applicable | not applicable |
| Base model, unconstrained decoding | 322 / 600 (53.7%) | 0 / 600 | 1.50 s |
| Adapter v2 | 357 / 600 (59.5%) | 600 / 600 | 0.93 s |
| Gold quote ceiling | 577 / 600 (96.2%) | not applicable | not applicable |

Not adopted: the registered adoption rule needs a gain over the base arm on the dev adoption
set, where every arm scores 200 of 200.

Reproduce with `python -m finetune.v2_data`, then `mlx_lm lora --config finetune/v2.yml`, then
`finetune/v2_evaluate.py` for each split and arm, then `python -m experiments.bench_v3 run` with
the `name=path` arms. Training used the MLX environment and local base weights described in
[`finetune/README.md`](../../README.md).
