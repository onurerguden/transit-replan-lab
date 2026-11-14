# TRL-Bench v3 · dev

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 400 | 210 (52.5%) | [47.1%, 57.6%] | 0 | 0.92% |
| lexicon | 400 | 220 (55.0%) | [49.8%, 60.0%] | 0 | 0.92% |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 400 | 400 (100.0%) | [100.0%, 100.0%] | 0 | 0.92% |
| s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 400 | 400 (100.0%) | [100.0%, 100.0%] | 0 | 0.92% |
| s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 400 | 398 (99.5%) | [98.7%, 100.0%] | 0 | 0.92% |
| base=experiments/results/v2_1/replies/base/dev.jsonl | 400 | 231 (57.8%) | [52.5%, 62.6%] | 0 | 0.92% |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 400 | 388 (97.0%) | [95.2%, 98.5%] | 0 | 0.92% |
| model_ceiling | 400 | 400 (100.0%) | [100.0%, 100.0%] | 0 | 0.92% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| rules vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 190 | 0.0000 | 0.0000 |
| rules vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 188 | 0.0000 | 0.0000 |
| lexicon vs rules | 10 | 0 | 0.0020 | 0.0176 |
| lexicon vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 180 | 0.0000 | 0.0000 |
| lexicon vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 178 | 0.0000 | 0.0000 |
| lexicon vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 2 | 170 | 0.0000 | 0.0000 |
| lexicon vs model_ceiling | 0 | 180 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs rules | 190 | 0 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs lexicon | 180 | 0 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 0 | 1.0000 | 1.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 2 | 0 | 0.5000 | 1.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs base=experiments/results/v2_1/replies/base/dev.jsonl | 169 | 0 | 0.0000 | 0.0000 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 12 | 0 | 0.0005 | 0.0059 |
| adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs model_ceiling | 0 | 0 | 1.0000 | 1.0000 |
| s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 2 | 0 | 0.5000 | 1.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs rules | 21 | 0 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs lexicon | 21 | 10 | 0.0708 | 0.4953 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 169 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 167 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 0 | 157 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs model_ceiling | 0 | 169 | 0.0000 | 0.0000 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs rules | 178 | 0 | 0.0000 | 0.0000 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 12 | 0.0005 | 0.0059 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 1 | 11 | 0.0063 | 0.0508 |
| model_ceiling vs rules | 190 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 0 | 1.0000 | 1.0000 |
| model_ceiling vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 2 | 0 | 0.5000 | 1.0000 |
| model_ceiling vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 12 | 0 | 0.0005 | 0.0059 |

## Accuracy by family

| Family | rules | lexicon | adapter=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | base=experiments/results/v2_1/replies/base/dev.jsonl | rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | model_ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 21/50 | 21/50 | 50/50 | 50/50 | 50/50 | 33/50 | 50/50 | 50/50 |
| closure_from | 23/50 | 24/50 | 50/50 | 50/50 | 50/50 | 26/50 | 50/50 | 50/50 |
| closure_note | 26/50 | 29/50 | 50/50 | 50/50 | 50/50 | 26/50 | 47/50 | 50/50 |
| closure_pair | 20/50 | 22/50 | 50/50 | 50/50 | 50/50 | 21/50 | 45/50 | 50/50 |
| closure_range | 21/50 | 24/50 | 50/50 | 50/50 | 50/50 | 23/50 | 50/50 | 50/50 |
| closure_until | 22/50 | 23/50 | 50/50 | 50/50 | 48/50 | 24/50 | 49/50 | 50/50 |
| hedged | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 |
| negated | 27/50 | 27/50 | 50/50 | 50/50 | 50/50 | 28/50 | 47/50 | 50/50 |
