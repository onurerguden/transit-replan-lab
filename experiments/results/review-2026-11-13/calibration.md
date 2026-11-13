# vNext intake and clarification evaluation

| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | Requested fields | Calls | p50 / p95 elapsed (ms) | p95 model (ms) | Unsupported | Hard violations | Difference vs rules (95% grouped interval) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| rules | 50/60 | 0/10 | 25/30 | 25/30 | 30 | 0 | 0.8 / 684.1 | 0 | 0 | 0 | [+0.0, +0.0] pp |
| lexicon | 60/60 | 10/10 | 30/30 | 30/30 | 20 | 0 | 1.8 / 704.5 | 0 | 0 | 0 | [+6.7, +30.0] pp |
| hybrid | 55/60 | 5/10 | 30/30 | 25/30 | 25 | 10 | 1.4 / 4017.7 | 5695 | 0 | 0 | [+3.3, +15.0] pp |
| adapter | 60/60 | 10/10 | 30/30 | 30/30 | 20 | 10 | 1.3 / 2266.5 | 2264 | 0 | 0 | [+6.7, +30.0] pp |

## Risk and coverage by evidence threshold

| Arm | Minimum evidence band | Automatically processed | Wrong event |
| --- | ---: | ---: | ---: |
| rules | 1 | 20/60 | 0/20 |
| rules | 2 | 20/60 | 0/20 |
| lexicon | 1 | 30/60 | 0/30 |
| lexicon | 2 | 30/60 | 0/30 |
| hybrid | 1 | 25/60 | 0/25 |
| hybrid | 2 | 20/60 | 0/20 |
| adapter | 1 | 30/60 | 0/30 |
| adapter | 2 | 20/60 | 0/20 |

Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.
