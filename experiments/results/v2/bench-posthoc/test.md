# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 2000 | 1076 (53.8%) | [49.7%, 57.7%] | 0 | 0.18% |
| lexicon | 2000 | 1076 (53.8%) | [49.7%, 57.7%] | 0 | 0.18% |
| model_ceiling | 2000 | 1923 (96.2%) | [95.0%, 97.3%] | 0 | 0.18% |
| model_adversarial | 2000 | 1217 (60.9%) | [56.1%, 64.7%] | 0 | 0.18% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 847 | 0.0000 | 0.0000 |
| lexicon vs model_adversarial | 152 | 293 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 847 | 0 | 0.0000 | 0.0000 |
| model_adversarial vs rules | 293 | 152 | 0.0000 | 0.0000 |
| model_adversarial vs model_ceiling | 22 | 728 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | model_adversarial |
| --- | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/154 | 0/154 | 154/154 | 55/154 |
| cancellation | 154/154 | 154/154 | 154/154 | 154/154 |
| closure_from | 0/154 | 0/154 | 154/154 | 52/154 |
| closure_note | 0/154 | 0/154 | 154/154 | 45/154 |
| closure_pair | 0/154 | 0/154 | 77/154 | 40/154 |
| closure_range | 0/154 | 0/154 | 154/154 | 47/154 |
| closure_until | 0/154 | 0/154 | 154/154 | 54/154 |
| delay | 154/154 | 154/154 | 154/154 | 154/154 |
| foreign_zone | 154/154 | 154/154 | 154/154 | 154/154 |
| hedged | 154/154 | 154/154 | 154/154 | 154/154 |
| negated | 154/154 | 154/154 | 154/154 | 154/154 |
| unrelated | 152/152 | 152/152 | 152/152 | 0/152 |
| wrong_date | 154/154 | 154/154 | 154/154 | 154/154 |
