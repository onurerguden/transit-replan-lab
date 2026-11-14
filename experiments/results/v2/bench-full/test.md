# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 2000 | 1076 (53.8%) | [49.7%, 57.7%] | 0 | 0.18% |
| lexicon | 2000 | 1076 (53.8%) | [49.7%, 57.7%] | 0 | 0.18% |
| model_ceiling | 2000 | 1923 (96.2%) | [95.0%, 97.3%] | 0 | 0.18% |
| seed42 | 2000 | 1191 (59.6%) | [55.1%, 63.8%] | 0 | 0.18% |
| seed43 | 2000 | 1606 (80.3%) | [77.3%, 83.5%] | 0 | 0.18% |
| seed44 | 2000 | 1569 (78.5%) | [74.1%, 82.7%] | 0 | 0.18% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| rules vs seed42 | 0 | 115 | 0.0000 | 0.0000 |
| rules vs seed43 | 0 | 530 | 0.0000 | 0.0000 |
| rules vs seed44 | 0 | 493 | 0.0000 | 0.0000 |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 847 | 0.0000 | 0.0000 |
| lexicon vs seed42 | 0 | 115 | 0.0000 | 0.0000 |
| lexicon vs seed43 | 0 | 530 | 0.0000 | 0.0000 |
| lexicon vs seed44 | 0 | 493 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 847 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs seed42 | 732 | 0 | 0.0000 | 0.0000 |
| model_ceiling vs seed43 | 362 | 45 | 0.0000 | 0.0000 |
| model_ceiling vs seed44 | 395 | 41 | 0.0000 | 0.0000 |
| seed42 vs seed43 | 23 | 438 | 0.0000 | 0.0000 |
| seed42 vs seed44 | 57 | 435 | 0.0000 | 0.0000 |
| seed43 vs seed44 | 164 | 127 | 0.0346 | 0.0693 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | seed42 | seed43 | seed44 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/154 | 0/154 | 154/154 | 109/154 | 87/154 | 52/154 |
| cancellation | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 |
| closure_from | 0/154 | 0/154 | 154/154 | 0/154 | 80/154 | 102/154 |
| closure_note | 0/154 | 0/154 | 154/154 | 1/154 | 97/154 | 76/154 |
| closure_pair | 0/154 | 0/154 | 77/154 | 0/154 | 92/154 | 93/154 |
| closure_range | 0/154 | 0/154 | 154/154 | 0/154 | 97/154 | 74/154 |
| closure_until | 0/154 | 0/154 | 154/154 | 5/154 | 77/154 | 96/154 |
| delay | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 |
| foreign_zone | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 |
| hedged | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 |
| negated | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 |
| unrelated | 152/152 | 152/152 | 152/152 | 152/152 | 152/152 | 152/152 |
| wrong_date | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 | 154/154 |
