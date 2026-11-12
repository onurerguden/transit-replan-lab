# vNext intake and clarification evaluation

| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | Requested fields | Calls | p95 model (ms) | Unsupported | Hard violations | Difference vs v1 (95% grouped interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| legacy | 46/120 | 0/20 | 23/60 | 23/60 | 282 | 0 | 0 | 0 | 0 | [+0.0, +0.0] pp |
| rules | 100/120 | 0/20 | 50/60 | 50/60 | 60 | 0 | 0 | 0 | 0 | [+33.3, +58.3] pp |
| hybrid | 120/120 | 20/20 | 60/60 | 60/60 | 40 | 20 | 2785 | 0 | 0 | [+48.3, +73.3] pp |
| generic | 100/120 | 0/20 | 50/60 | 50/60 | 180 | 0 | 0 | 0 | 0 | [+33.3, +58.3] pp |
| fixed | 100/120 | 0/20 | 50/60 | 50/60 | 60 | 0 | 0 | 0 | 0 | [+33.3, +58.3] pp |
| adapter | 120/120 | 20/20 | 60/60 | 60/60 | 40 | 20 | 2185 | 0 | 0 | [+48.3, +73.3] pp |

## Risk and coverage by evidence threshold

| Arm | Minimum evidence band | Automatically processed | Wrong event |
| --- | ---: | ---: | ---: |
| rules | 1 | 40/120 | 0/40 |
| rules | 2 | 40/120 | 0/40 |
| hybrid | 1 | 60/120 | 0/60 |
| hybrid | 2 | 40/120 | 0/40 |
| adapter | 1 | 60/120 | 0/60 |
| adapter | 2 | 40/120 | 0/40 |

Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.
