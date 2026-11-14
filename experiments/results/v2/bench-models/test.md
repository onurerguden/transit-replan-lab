# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 600 | 322 (53.7%) | [46.6%, 61.4%] | 0 | 0.61% |
| lexicon | 600 | 322 (53.7%) | [46.6%, 61.4%] | 0 | 0.61% |
| model_ceiling | 600 | 577 (96.2%) | [93.9%, 98.3%] | 0 | 0.61% |
| adapter | 600 | 357 (59.5%) | [52.4%, 67.1%] | 0 | 0.61% |
| base | 600 | 322 (53.7%) | [46.6%, 61.4%] | 0 | 0.61% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 255 | 0.0000 | 0.0000 |
| model_ceiling vs rules | 255 | 0 | 0.0000 | 0.0000 |
| adapter vs rules | 35 | 0 | 0.0000 | 0.0000 |
| adapter vs lexicon | 35 | 0 | 0.0000 | 0.0000 |
| adapter vs model_ceiling | 0 | 220 | 0.0000 | 0.0000 |
| adapter vs base | 35 | 0 | 0.0000 | 0.0000 |
| base vs rules | 0 | 0 | 1.0000 | 1.0000 |
| base vs lexicon | 0 | 0 | 1.0000 | 1.0000 |
| base vs model_ceiling | 0 | 255 | 0.0000 | 0.0000 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | adapter | base |
| --- | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/46 | 0/46 | 46/46 | 33/46 | 0/46 |
| cancellation | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
| closure_from | 0/46 | 0/46 | 46/46 | 0/46 | 0/46 |
| closure_note | 0/46 | 0/46 | 46/46 | 0/46 | 0/46 |
| closure_pair | 0/46 | 0/46 | 23/46 | 0/46 | 0/46 |
| closure_range | 0/48 | 0/48 | 48/48 | 0/48 | 0/48 |
| closure_until | 0/46 | 0/46 | 46/46 | 2/46 | 0/46 |
| delay | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
| foreign_zone | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
| hedged | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
| negated | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
| unrelated | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
| wrong_date | 46/46 | 46/46 | 46/46 | 46/46 | 46/46 |
