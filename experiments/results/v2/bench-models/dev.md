# TRL-Bench v3 · dev

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 200 | 200 (100.0%) | [100.0%, 100.0%] | 0 | 1.83% |
| lexicon | 200 | 200 (100.0%) | [100.0%, 100.0%] | 0 | 1.83% |
| model_ceiling | 200 | 200 (100.0%) | [100.0%, 100.0%] | 0 | 1.83% |
| adapter | 200 | 200 (100.0%) | [100.0%, 100.0%] | 0 | 1.83% |
| base | 200 | 200 (100.0%) | [100.0%, 100.0%] | 0 | 1.83% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| lexicon vs rules | 0 | 0 | 1.0000 | 1.0000 |
| lexicon vs model_ceiling | 0 | 0 | 1.0000 | 1.0000 |
| model_ceiling vs rules | 0 | 0 | 1.0000 | 1.0000 |
| adapter vs rules | 0 | 0 | 1.0000 | 1.0000 |
| adapter vs lexicon | 0 | 0 | 1.0000 | 1.0000 |
| adapter vs model_ceiling | 0 | 0 | 1.0000 | 1.0000 |
| adapter vs base | 0 | 0 | 1.0000 | 1.0000 |
| base vs rules | 0 | 0 | 1.0000 | 1.0000 |
| base vs lexicon | 0 | 0 | 1.0000 | 1.0000 |
| base vs model_ceiling | 0 | 0 | 1.0000 | 1.0000 |

## Accuracy by family

| Family | rules | lexicon | model_ceiling | adapter | base |
| --- | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 14/14 | 14/14 | 14/14 | 14/14 | 14/14 |
| cancellation | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| closure_from | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| closure_note | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| closure_pair | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| closure_range | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| closure_until | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| delay | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| foreign_zone | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| hedged | 14/14 | 14/14 | 14/14 | 14/14 | 14/14 |
| negated | 14/14 | 14/14 | 14/14 | 14/14 | 14/14 |
| unrelated | 16/16 | 16/16 | 16/16 | 16/16 | 16/16 |
| wrong_date | 14/14 | 14/14 | 14/14 | 14/14 | 14/14 |
