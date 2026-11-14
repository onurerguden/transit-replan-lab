# TRL-Bench v3 · test

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 600 | 322 (53.7%) | [46.6%, 61.4%] | 0 | 0.61% |
| seed42 | 600 | 357 (59.5%) | [52.4%, 67.1%] | 0 | 0.61% |
| seed43 | 600 | 466 (77.7%) | [72.6%, 82.5%] | 0 | 0.61% |
| seed44 | 600 | 461 (76.8%) | [70.9%, 82.2%] | 0 | 0.61% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| rules vs seed42 | 0 | 35 | 0.0000 | 0.0000 |
| rules vs seed43 | 0 | 144 | 0.0000 | 0.0000 |
| rules vs seed44 | 0 | 139 | 0.0000 | 0.0000 |
| seed42 vs seed43 | 7 | 116 | 0.0000 | 0.0000 |
| seed42 vs seed44 | 15 | 119 | 0.0000 | 0.0000 |
| seed43 vs seed44 | 52 | 47 | 0.6879 | 0.6879 |

## Accuracy by family

| Family | rules | seed42 | seed43 | seed44 |
| --- | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/46 | 33/46 | 26/46 | 18/46 |
| cancellation | 46/46 | 46/46 | 46/46 | 46/46 |
| closure_from | 0/46 | 0/46 | 25/46 | 28/46 |
| closure_note | 0/46 | 0/46 | 21/46 | 16/46 |
| closure_pair | 0/46 | 0/46 | 21/46 | 25/46 |
| closure_range | 0/48 | 0/48 | 29/48 | 21/48 |
| closure_until | 0/46 | 2/46 | 22/46 | 31/46 |
| delay | 46/46 | 46/46 | 46/46 | 46/46 |
| foreign_zone | 46/46 | 46/46 | 46/46 | 46/46 |
| hedged | 46/46 | 46/46 | 46/46 | 46/46 |
| negated | 46/46 | 46/46 | 46/46 | 46/46 |
| unrelated | 46/46 | 46/46 | 46/46 | 46/46 |
| wrong_date | 46/46 | 46/46 | 46/46 | 46/46 |
