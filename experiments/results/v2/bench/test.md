# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 2000 | 1028 (51.4%) | [47.0%, 55.7%] | 0 | 0.18% |
| lexicon | 2000 | 1028 (51.4%) | [47.0%, 55.7%] | 0 | 0.18% |
| model_ceiling | 2000 | 1682 (84.1%) | [79.7%, 88.3%] | 0 | 0.18% |
| model_adversarial | 2000 | 1122 (56.1%) | [51.0%, 60.6%] | 0 | 0.18% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 654 | 0.0000 | 0.0000 |
| lexicon vs model_adversarial | 122 | 216 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 654 | 0 | 0.0000 | 0.0000 |
| model_adversarial vs rules | 216 | 122 | 0.0000 | 0.0000 |
| model_adversarial vs model_ceiling | 3 | 563 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | model_adversarial |
| --- | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/154 | 0/154 | 121/154 | 47/154 |
| cancellation | 134/154 | 134/154 | 134/154 | 134/154 |
| closure_from | 0/154 | 0/154 | 136/154 | 44/154 |
| closure_note | 0/154 | 0/154 | 128/154 | 40/154 |
| closure_pair | 0/154 | 0/154 | 0/154 | 0/154 |
| closure_range | 0/154 | 0/154 | 137/154 | 40/154 |
| closure_until | 0/154 | 0/154 | 132/154 | 45/154 |
| delay | 126/154 | 126/154 | 126/154 | 126/154 |
| foreign_zone | 154/154 | 154/154 | 154/154 | 154/154 |
| hedged | 154/154 | 154/154 | 154/154 | 154/154 |
| negated | 154/154 | 154/154 | 154/154 | 154/154 |
| unrelated | 152/152 | 152/152 | 152/152 | 30/152 |
| wrong_date | 154/154 | 154/154 | 154/154 | 154/154 |
