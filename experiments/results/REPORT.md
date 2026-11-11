# Comparative evaluation

Verified and correct is evaluated on reference-feasible cases. Gap and delay use successful cases with a reference meeting time.

## Dev

| Coordinator | N | Verified and correct | Outcome correct | Clarification | Hard violations | Median gap | Median recovery delay | Mean calls | Mean tokens | p95 | Δ vs rules, 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | 24 | 14/14 | 24/24 | 4/4 | 0 | 0 s | 0 s | 0.00 | 0 | 0.38 s | [+0.0, +0.0] pp |
| single | 24 | 14/14 | 20/24 | 0/4 | 0 | 0 s | 450 s | 1.75 | 1171 | 6.45 s | [+0.0, +0.0] pp |
| three | 24 | 14/14 | 20/24 | 0/4 | 0 | 28 s | 435 s | 4.33 | 2402 | 15.01 s | [+0.0, +0.0] pp |
| five | 24 | 14/14 | 20/24 | 0/4 | 0 | 0 s | 210 s | 5.08 | 2631 | 11.68 s | [+0.0, +0.0] pp |

## Locked

| Coordinator | N | Verified and correct | Outcome correct | Clarification | Hard violations | Median gap | Median recovery delay | Mean calls | Mean tokens | p95 | Δ vs rules, 95% CI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | 60 | 33/38 | 55/60 | 10/10 | 0 | 0 s | 0 s | 0.00 | 0 | 0.33 s | [+0.0, +0.0] pp |
| single | 60 | 38/38 | 60/60 | 10/10 | 0 | 0 s | 210 s | 1.63 | 1136 | 6.73 s | [+2.6, +26.3] pp |
| three | 60 | 36/38 | 58/60 | 10/10 | 0 | 6 s | 450 s | 3.90 | 2245 | 15.52 s | [-5.3, +21.1] pp |
| five | 60 | 38/38 | 60/60 | 10/10 | 0 | 0 s | 0 s | 4.28 | 2360 | 10.97 s | [+2.6, +26.3] pp |
| five-no-counter | 12 | 10/10 | 12/12 | 0/0 | 0 | 0 s | 2250 s | 5.50 | 2866 | 6.33 s | [+0.0, +0.0] pp |

## Correct intake by language

| Coordinator | Turkish | English |
| --- | ---: | ---: |
| rules | 30/30 | 25/30 |
| single | 30/30 | 30/30 |
| three | 30/30 | 30/30 |
| five | 30/30 | 30/30 |

## Counteroffer ablation

Across 12 matched cases, five roles succeeded 10 times with counteroffers and 10 times with a single round.

## Failure examples

- `locked-interchange-03` / three ended with `no_agreement` against expected `feasible`. Incident exact match was true.
- `locked-platform-07` / three ended with `model_error` against expected `feasible`. Incident exact match was true. The error code was `invalid_vote`.
- `locked-delay-01` / rules ended with `clarification` against expected `feasible`. Incident exact match was false.
- `locked-delay-03` / rules ended with `clarification` against expected `feasible`. Incident exact match was false.
