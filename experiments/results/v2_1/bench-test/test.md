# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 616 | 50 (8.1%) | [5.7%, 10.9%] | 0 | 0.60% |
| lexicon | 616 | 50 (8.1%) | [5.7%, 10.9%] | 0 | 0.60% |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl | 616 | 552 (89.6%) | [87.2%, 92.0%] | 0 | 0.60% |
| base=experiments/results/v2_1/replies/base/test.jsonl | 616 | 112 (18.2%) | [14.9%, 21.8%] | 2 | 1.17% |
| rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl | 616 | 516 (83.8%) | [80.7%, 86.6%] | 0 | 0.60% |
| model_ceiling | 616 | 616 (100.0%) | [100.0%, 100.0%] | 0 | 0.60% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl | 0 | 466 | 0.0000 | 0.0000 |
| lexicon vs model_ceiling | 0 | 566 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs rules | 502 | 0 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs lexicon | 502 | 0 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs base=experiments/results/v2_1/replies/base/test.jsonl | 443 | 3 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl | 70 | 34 | 0.0005 | 0.0011 |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs model_ceiling | 0 | 64 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/test.jsonl vs rules | 62 | 0 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/test.jsonl vs lexicon | 62 | 0 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/test.jsonl vs rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl | 10 | 414 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/test.jsonl vs model_ceiling | 0 | 504 | 0.0000 | 0.0000 |
| rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl vs rules | 466 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 566 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl | 100 | 0 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl | base=experiments/results/v2_1/replies/base/test.jsonl | rag4=experiments/results/v2_1/replies/base_rag4/test.jsonl | model_ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/76 | 0/76 | 62/76 | 16/76 | 55/76 | 76/76 |
| closure_from | 0/78 | 0/78 | 70/78 | 6/78 | 65/78 | 78/78 |
| closure_note | 0/76 | 0/76 | 73/76 | 3/76 | 64/76 | 76/76 |
| closure_pair | 0/78 | 0/78 | 72/78 | 11/78 | 63/78 | 78/78 |
| closure_range | 0/78 | 0/78 | 71/78 | 8/78 | 61/78 | 78/78 |
| closure_until | 0/76 | 0/76 | 62/76 | 2/76 | 69/76 | 76/76 |
| hedged | 38/76 | 38/76 | 73/76 | 50/76 | 75/76 | 76/76 |
| negated | 12/78 | 12/78 | 69/78 | 16/78 | 64/78 | 78/78 |
