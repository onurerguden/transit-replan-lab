# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl | 616 | 552 (89.6%) | [87.2%, 92.0%] | 0 | 0.60% |
| s43=experiments/results/v2_1/replies/adapter_s43/test.jsonl | 616 | 568 (92.2%) | [89.9%, 94.3%] | 0 | 0.60% |
| s44=experiments/results/v2_1/replies/adapter_s44/test.jsonl | 616 | 548 (89.0%) | [86.4%, 91.4%] | 0 | 0.60% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs s43=experiments/results/v2_1/replies/adapter_s43/test.jsonl | 16 | 32 | 0.0293 | 0.0586 |
| adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/test.jsonl | 27 | 23 | 0.6718 | 0.6718 |
| s43=experiments/results/v2_1/replies/adapter_s43/test.jsonl vs s44=experiments/results/v2_1/replies/adapter_s44/test.jsonl | 41 | 21 | 0.0151 | 0.0454 |

## Accuracy by family

| Family | adapter=experiments/results/v2_1/replies/adapter_s42/test.jsonl | s43=experiments/results/v2_1/replies/adapter_s43/test.jsonl | s44=experiments/results/v2_1/replies/adapter_s44/test.jsonl |
| --- | ---: | ---: | ---: |
| ambiguous_stop | 62/76 | 65/76 | 57/76 |
| closure_from | 70/78 | 66/78 | 71/78 |
| closure_note | 73/76 | 72/76 | 70/76 |
| closure_pair | 72/78 | 73/78 | 74/78 |
| closure_range | 71/78 | 72/78 | 65/78 |
| closure_until | 62/76 | 71/76 | 65/76 |
| hedged | 73/76 | 75/76 | 71/76 |
| negated | 69/78 | 74/78 | 75/78 |
