# vNext intake and clarification evaluation

| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | Requested fields | Calls | p50 / p95 elapsed (ms) | p95 model (ms) | Unsupported | Hard violations | Difference vs rules (95% grouped interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| rules | 66/80 | 0/14 | 33/40 | 33/40 | 40 | 0 | 0.8 / 541.1 | 0 | 0 | 0 | [+0.0, +0.0] pp |
| lexicon | 80/80 | 14/14 | 40/40 | 40/40 | 26 | 0 | 1.5 / 538.5 | 0 | 0 | 0 | [+7.5, +30.0] pp |
| hybrid | 80/80 | 14/14 | 40/40 | 40/40 | 26 | 14 | 1.6 / 3222.6 | 3306 | 0 | 0 | [+7.5, +30.0] pp |
| adapter | 80/80 | 14/14 | 40/40 | 40/40 | 26 | 14 | 1.4 / 2314.5 | 3041 | 0 | 0 | [+7.5, +30.0] pp |

## Risk and coverage by evidence threshold

| Arm | Minimum evidence band | Automatically processed | Wrong event |
| --- | ---: | ---: | ---: |
| rules | 1 | 28/80 | 0/28 |
| rules | 2 | 28/80 | 0/28 |
| lexicon | 1 | 42/80 | 0/42 |
| lexicon | 2 | 42/80 | 0/42 |
| hybrid | 1 | 42/80 | 0/42 |
| hybrid | 2 | 28/80 | 0/28 |
| adapter | 1 | 42/80 | 0/42 |
| adapter | 2 | 28/80 | 0/28 |

Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.
