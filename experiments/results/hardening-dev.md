# Comparative evaluation

Verified and correct is evaluated on reference-feasible cases. Gap and delay use successful cases with a reference meeting time.

## Dev

| Coordinator | N | Verified and correct | Outcome correct | Clarification | Hard violations | Median gap | Median recovery delay | Mean calls | Mean tokens | p95 | Δ vs rules, 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | 24 | 14/14 | 24/24 | 4/4 | 0 | 0 s | 0 s | 0.00 | 0 | 0.37 s | [+0.0, +0.0] pp |
| single | 24 | 14/14 | 24/24 | 4/4 | 0 | 0 s | 450 s | 1.58 | 1105 | 7.92 s | [+0.0, +0.0] pp |
| three | 24 | 14/14 | 24/24 | 4/4 | 0 | 28 s | 435 s | 3.58 | 2049 | 18.04 s | [+0.0, +0.0] pp |
| five | 24 | 14/14 | 24/24 | 4/4 | 0 | 0 s | 210 s | 4.08 | 2205 | 14.56 s | [+0.0, +0.0] pp |
