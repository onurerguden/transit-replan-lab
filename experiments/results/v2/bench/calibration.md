# TRL-Bench v3 · calibration

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 600 | 600 (100.0%) | [100.0%, 100.0%] | 0 | 0.61% |
| lexicon | 600 | 600 (100.0%) | [100.0%, 100.0%] | 0 | 0.61% |
| model_ceiling | 600 | 600 (100.0%) | [100.0%, 100.0%] | 0 | 0.61% |
| model_adversarial | 600 | 577 (96.2%) | [67.1%, 100.0%] | 0 | 0.61% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_adversarial | 23 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 0 | 0 | 1.0000 | 1.0000 |
| model_adversarial vs rules | 0 | 23 | 0.0000 | 0.0000 |
| model_adversarial vs model_ceiling | 0 | 23 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | model_adversarial |
| --- | ---: | ---: | ---: | ---: |
| ambiguous_stop | 46/46 | 46/46 | 46/46 | 46/46 |
| cancellation | 46/46 | 46/46 | 46/46 | 46/46 |
| closure_from | 46/46 | 46/46 | 46/46 | 46/46 |
| closure_note | 46/46 | 46/46 | 46/46 | 46/46 |
| closure_pair | 46/46 | 46/46 | 46/46 | 46/46 |
| closure_range | 48/48 | 48/48 | 48/48 | 48/48 |
| closure_until | 46/46 | 46/46 | 46/46 | 46/46 |
| delay | 46/46 | 46/46 | 46/46 | 46/46 |
| foreign_zone | 46/46 | 46/46 | 46/46 | 46/46 |
| hedged | 46/46 | 46/46 | 46/46 | 46/46 |
| negated | 46/46 | 46/46 | 46/46 | 46/46 |
| unrelated | 46/46 | 46/46 | 46/46 | 23/46 |
| wrong_date | 46/46 | 46/46 | 46/46 | 46/46 |
