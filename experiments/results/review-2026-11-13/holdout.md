# vNext intake and clarification evaluation

| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | Requested fields | Calls | p50 / p95 elapsed (ms) | p95 model (ms) | Unsupported | Hard violations | Difference vs rules (95% grouped interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| rules | 16/24 | 0/4 | 8/12 | 8/12 | 8 | 0 | 0.6 / 388.1 | 0 | 0 | 0 | [+0.0, +0.0] pp |
| lexicon | 19/24 | 3/4 | 10/12 | 9/12 | 5 | 0 | 1.3 / 380.7 | 0 | 0 | 0 | [+0.0, +33.3] pp |
| hybrid | 19/24 | 3/4 | 10/12 | 9/12 | 5 | 8 | 363.2 / 4231.2 | 4259 | 0 | 0 | [+0.0, +33.3] pp |
| adapter | 19/24 | 3/4 | 10/12 | 9/12 | 5 | 8 | 366.8 / 4432.9 | 4431 | 0 | 0 | [+0.0, +33.3] pp |

## Risk and coverage by evidence threshold

| Arm | Minimum evidence band | Automatically processed | Wrong event |
| --- | ---: | ---: | ---: |
| rules | 1 | 10/24 | 0/10 |
| rules | 2 | 10/24 | 0/10 |
| lexicon | 1 | 13/24 | 0/13 |
| lexicon | 2 | 13/24 | 0/13 |
| hybrid | 1 | 13/24 | 0/13 |
| hybrid | 2 | 10/24 | 0/10 |
| adapter | 1 | 13/24 | 0/13 |
| adapter | 2 | 10/24 | 0/10 |

Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.
