# vNext intake and clarification evaluation

| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | Requested fields | Calls | p95 model (ms) | Unsupported | Hard violations | Difference vs v1 (95% grouped interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| legacy | 30/80 | 0/14 | 15/40 | 15/40 | 186 | 0 | 0 | 0 | 0 | [+0.0, +0.0] pp |
| rules | 66/80 | 0/14 | 33/40 | 33/40 | 40 | 0 | 0 | 0 | 0 | [+30.0, +60.0] pp |
| hybrid | 80/80 | 14/14 | 40/40 | 40/40 | 26 | 14 | 5910 | 0 | 0 | [+47.5, +77.5] pp |
| generic | 66/80 | 0/14 | 33/40 | 33/40 | 120 | 0 | 0 | 0 | 0 | [+30.0, +60.0] pp |
| fixed | 66/80 | 0/14 | 33/40 | 33/40 | 40 | 0 | 0 | 0 | 0 | [+30.0, +60.0] pp |
| adapter | 80/80 | 14/14 | 40/40 | 40/40 | 26 | 14 | 4227 | 0 | 0 | [+47.5, +77.5] pp |

## Risk and coverage by evidence threshold

| Arm | Minimum evidence band | Automatically processed | Wrong event |
| --- | ---: | ---: | ---: |
| rules | 1 | 28/80 | 0/28 |
| rules | 2 | 28/80 | 0/28 |
| hybrid | 1 | 42/80 | 0/42 |
| hybrid | 2 | 28/80 | 0/28 |
| adapter | 1 | 42/80 | 0/42 |
| adapter | 2 | 28/80 | 0/28 |

Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.
