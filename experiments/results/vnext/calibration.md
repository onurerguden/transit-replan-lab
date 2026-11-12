# vNext intake and clarification evaluation

| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | Requested fields | Calls | p95 model (ms) | Unsupported | Hard violations | Difference vs v1 (95% grouped interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| legacy | 24/60 | 0/10 | 12/30 | 12/30 | 138 | 0 | 0 | 0 | 0 | [+0.0, +0.0] pp |
| rules | 50/60 | 0/10 | 25/30 | 25/30 | 30 | 0 | 0 | 0 | 0 | [+26.7, +60.0] pp |
| hybrid | 55/60 | 5/10 | 30/30 | 25/30 | 25 | 10 | 6705 | 0 | 0 | [+35.0, +68.3] pp |
| generic | 50/60 | 0/10 | 25/30 | 25/30 | 90 | 0 | 0 | 0 | 0 | [+26.7, +60.0] pp |
| fixed | 50/60 | 0/10 | 25/30 | 25/30 | 30 | 0 | 0 | 0 | 0 | [+26.7, +60.0] pp |
| adapter | 60/60 | 10/10 | 30/30 | 30/30 | 20 | 10 | 3917 | 0 | 0 | [+43.3, +76.7] pp |

## Risk and coverage by evidence threshold

| Arm | Minimum evidence band | Automatically processed | Wrong event |
| --- | ---: | ---: | ---: |
| rules | 1 | 20/60 | 0/20 |
| rules | 2 | 20/60 | 0/20 |
| hybrid | 1 | 25/60 | 0/25 |
| hybrid | 2 | 20/60 | 0/20 |
| adapter | 1 | 30/60 | 0/30 |
| adapter | 2 | 20/60 | 0/20 |

Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.
