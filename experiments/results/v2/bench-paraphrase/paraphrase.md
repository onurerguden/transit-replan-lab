# TRL-Bench v3 · paraphrase

| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |
| --- | ---: | ---: | --- | ---: | ---: |
| rules | 438 | 161 (36.8%) | [32.4%, 41.1%] | 36 | 11.20% |
| lexicon | 438 | 165 (37.7%) | [33.1%, 42.0%] | 39 | 11.97% |
| seed42 | 438 | 192 (43.8%) | [39.0%, 48.6%] | 36 | 11.20% |
| seed43 | 438 | 212 (48.4%) | [43.8%, 52.7%] | 44 | 13.25% |
| seed44 | 438 | 231 (52.7%) | [48.2%, 57.3%] | 41 | 12.48% |

## Paired contrasts (exact McNemar, Holm-adjusted)

| Contrast | Only left right | Only right right | p | Holm p |
| --- | ---: | ---: | ---: | ---: |
| rules vs seed42 | 0 | 31 | 0.0000 | 0.0000 |
| rules vs seed43 | 0 | 51 | 0.0000 | 0.0000 |
| rules vs seed44 | 0 | 70 | 0.0000 | 0.0000 |
| lexicon vs rules | 4 | 0 | 0.1250 | 0.1250 |
| lexicon vs seed42 | 4 | 31 | 0.0000 | 0.0000 |
| lexicon vs seed43 | 3 | 50 | 0.0000 | 0.0000 |
| lexicon vs seed44 | 4 | 70 | 0.0000 | 0.0000 |
| seed42 vs seed43 | 7 | 27 | 0.0008 | 0.0025 |
| seed42 vs seed44 | 8 | 47 | 0.0000 | 0.0000 |
| seed43 vs seed44 | 15 | 34 | 0.0094 | 0.0188 |

## Accuracy by family

| Family | rules | lexicon | seed42 | seed43 | seed44 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 8/40 | 8/40 | 19/40 | 14/40 | 12/40 |
| cancellation | 15/36 | 15/36 | 33/36 | 31/36 | 32/36 |
| closure_from | 11/36 | 11/36 | 11/36 | 14/36 | 24/36 |
| closure_note | 2/26 | 4/26 | 2/26 | 5/26 | 5/26 |
| closure_pair | 8/44 | 9/44 | 9/44 | 21/44 | 26/44 |
| closure_range | 15/40 | 16/40 | 15/40 | 21/40 | 20/40 |
| closure_until | 11/36 | 11/36 | 11/36 | 14/36 | 19/36 |
| delay | 20/32 | 20/32 | 21/32 | 21/32 | 21/32 |
| foreign_zone | 13/34 | 13/34 | 13/34 | 13/34 | 13/34 |
| hedged | 15/38 | 15/38 | 15/38 | 15/38 | 15/38 |
| negated | 7/40 | 7/40 | 7/40 | 7/40 | 8/40 |
| wrong_date | 36/36 | 36/36 | 36/36 | 36/36 | 36/36 |
