# TRL-Bench v3 · dev

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 1200 | 1200 (100.0%) | [100.0%, 100.0%] | 0 | 0.31% |
| lexicon | 1200 | 1200 (100.0%) | [100.0%, 100.0%] | 0 | 0.31% |
| model_ceiling | 1200 | 1200 (100.0%) | [100.0%, 100.0%] | 0 | 0.31% |
| model_adversarial | 1200 | 1145 (95.4%) | [89.1%, 98.5%] | 0 | 0.31% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_adversarial | 55 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 0 | 0 | 1.0000 | 1.0000 |
| model_adversarial vs rules | 0 | 55 | 0.0000 | 0.0000 |
| model_adversarial vs model_ceiling | 0 | 55 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | model_adversarial |
| --- | ---: | ---: | ---: | ---: |
| ambiguous_stop | 92/92 | 92/92 | 92/92 | 92/92 |
| cancellation | 92/92 | 92/92 | 92/92 | 92/92 |
| closure_from | 92/92 | 92/92 | 92/92 | 92/92 |
| closure_note | 92/92 | 92/92 | 92/92 | 92/92 |
| closure_pair | 92/92 | 92/92 | 92/92 | 92/92 |
| closure_range | 94/94 | 94/94 | 94/94 | 94/94 |
| closure_until | 94/94 | 94/94 | 94/94 | 94/94 |
| delay | 92/92 | 92/92 | 92/92 | 92/92 |
| foreign_zone | 92/92 | 92/92 | 92/92 | 92/92 |
| hedged | 92/92 | 92/92 | 92/92 | 92/92 |
| negated | 92/92 | 92/92 | 92/92 | 92/92 |
| unrelated | 92/92 | 92/92 | 92/92 | 37/92 |
| wrong_date | 92/92 | 92/92 | 92/92 | 92/92 |
