# TRL-Bench v3 · dev

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 400 | 210 (52.5%) | [47.1%, 57.6%] | 0 | 0.92% |
| lexicon | 400 | 220 (55.0%) | [49.8%, 60.0%] | 0 | 0.92% |
| s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 400 | 243 (60.8%) | [55.4%, 66.1%] | 0 | 0.92% |
| s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 400 | 243 (60.8%) | [55.4%, 66.1%] | 0 | 0.92% |
| s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 400 | 250 (62.5%) | [57.0%, 67.7%] | 0 | 0.92% |
| base=experiments/results/v2_1/replies/base/dev.jsonl | 400 | 214 (53.5%) | [48.1%, 58.6%] | 0 | 0.92% |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl | 400 | 239 (59.8%) | [54.4%, 65.1%] | 0 | 0.92% |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 400 | 238 (59.5%) | [54.0%, 64.8%] | 0 | 0.92% |
| rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | 400 | 236 (59.0%) | [53.6%, 64.2%] | 0 | 0.92% |
| model_ceiling | 400 | 400 (100.0%) | [100.0%, 100.0%] | 0 | 0.92% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| rules vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 0 | 33 | 0.0000 | 0.0000 |
| rules vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 33 | 0.0000 | 0.0000 |
| rules vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 40 | 0.0000 | 0.0000 |
| lexicon vs rules | 10 | 0 | 0.0020 | 0.0293 |
| lexicon vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 0 | 23 | 0.0000 | 0.0000 |
| lexicon vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 23 | 0.0000 | 0.0000 |
| lexicon vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 30 | 0.0000 | 0.0000 |
| lexicon vs rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl | 0 | 19 | 0.0000 | 0.0001 |
| lexicon vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 2 | 20 | 0.0001 | 0.0024 |
| lexicon vs rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | 1 | 17 | 0.0001 | 0.0026 |
| lexicon vs model_ceiling | 0 | 180 | 0.0000 | 0.0000 |
| s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 0 | 1.0000 | 1.0000 |
| s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 7 | 0.0156 | 0.2188 |
| s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 7 | 0.0156 | 0.2188 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs rules | 4 | 0 | 0.1250 | 0.8750 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs lexicon | 1 | 7 | 0.0703 | 0.6250 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 0 | 29 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 29 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 36 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl | 0 | 25 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 1 | 25 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | 0 | 22 | 0.0000 | 0.0000 |
| base=experiments/results/v2_1/replies/base/dev.jsonl vs model_ceiling | 0 | 186 | 0.0000 | 0.0000 |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl vs rules | 29 | 0 | 0.0000 | 0.0000 |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 0 | 4 | 0.1250 | 0.8750 |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 4 | 0.1250 | 0.8750 |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 11 | 0.0010 | 0.0156 |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 3 | 2 | 1.0000 | 1.0000 |
| rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl vs rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | 4 | 1 | 0.3750 | 1.0000 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs rules | 28 | 0 | 0.0000 | 0.0000 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 0 | 5 | 0.0625 | 0.6250 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 5 | 0.0625 | 0.6250 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 12 | 0.0005 | 0.0083 |
| rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl vs rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | 3 | 1 | 0.6250 | 1.0000 |
| rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl vs rules | 26 | 0 | 0.0000 | 0.0000 |
| rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 0 | 7 | 0.0156 | 0.2188 |
| rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 0 | 7 | 0.0156 | 0.2188 |
| rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 0 | 14 | 0.0001 | 0.0024 |
| model_ceiling vs rules | 190 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | 157 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | 157 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | 150 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl | 161 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | 162 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | 164 | 0 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | s42=experiments/results/v2_1/replies/adapter_s42/dev.jsonl | s43=experiments/results/v2_1/replies/adapter_s43/dev.jsonl | s44=experiments/results/v2_1/replies/adapter_s44/dev.jsonl | base=experiments/results/v2_1/replies/base/dev.jsonl | rag2=experiments/results/v2_1/replies/base_rag2/dev.jsonl | rag4=experiments/results/v2_1/replies/base_rag4/dev.jsonl | rag8=experiments/results/v2_1/replies/base_rag8/dev.jsonl | model_ceiling |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 21/50 | 21/50 | 21/50 | 21/50 | 21/50 | 21/50 | 21/50 | 21/50 | 21/50 | 50/50 |
| closure_from | 23/50 | 24/50 | 24/50 | 24/50 | 24/50 | 23/50 | 24/50 | 24/50 | 24/50 | 50/50 |
| closure_note | 26/50 | 29/50 | 29/50 | 29/50 | 34/50 | 28/50 | 29/50 | 28/50 | 29/50 | 50/50 |
| closure_pair | 20/50 | 22/50 | 22/50 | 22/50 | 23/50 | 20/50 | 22/50 | 21/50 | 21/50 | 50/50 |
| closure_range | 21/50 | 24/50 | 24/50 | 24/50 | 25/50 | 22/50 | 24/50 | 24/50 | 24/50 | 50/50 |
| closure_until | 22/50 | 23/50 | 23/50 | 23/50 | 23/50 | 22/50 | 23/50 | 23/50 | 23/50 | 50/50 |
| hedged | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 | 50/50 |
| negated | 27/50 | 27/50 | 50/50 | 50/50 | 50/50 | 28/50 | 46/50 | 47/50 | 44/50 | 50/50 |
