# Operator adapter v2

See [ADR 0016](../../../docs/adr/0016-operator-adapter-v2.md) for the decision and
[`training.json`](training.json) for the run. Replies and scores are in
[`experiments/results/v2/bench-models`](../../../experiments/results/v2/bench-models).

| Arm | Test subset correct | Schema-valid replies | p50 latency |
| --- | ---: | ---: | ---: |
| Rules and phrase list | 322 / 600 (53.7%) | not applicable | not applicable |
| Base model, unconstrained decoding | 322 / 600 (53.7%) | 0 / 600 | 1.50 s |
| Adapter v2, seed 42 | 357 / 600 (59.5%) | 600 / 600 | 0.93 s |
| Adapter v2, seed 43 | 466 / 600 (77.7%) | 600 / 600 | not recorded here |
| Adapter v2, seed 44 | 461 / 600 (76.8%) | 600 / 600 | not recorded here |
| Gold quote ceiling | 577 / 600 (96.2%) | not applicable | not applicable |

Seed variance is large: seed 42 differs from seeds 43 and 44 by about 18 points, while 43 and 44 do not differ (exact p 0.69). Scores for all seeds are in [`bench-seeds`](../../../experiments/results/v2/bench-seeds/test.md). Not adopted: the registered adoption rule needs a gain over the base arm on the dev adoption
set, where every arm scores 200 of 200.

Reproduce with `python -m finetune.v2_data`, then `mlx_lm lora --config finetune/v2.yml`, then
`finetune/v2_evaluate.py` for each split and arm, then `python -m experiments.bench_v3 run` with
the `name=path` arms. Training used the MLX environment and local base weights described in
[`finetune/README.md`](../../README.md).
