# v2 baseline

Recorded on 2026-11-13 before any v2 behavior change.

| Item | Value |
| --- | --- |
| Baseline commit | `1dfe799` (`origin/main`, tag `v1.2.0`). The tree is identical to `f8a8110`. |
| Branch | `feat/v2-engineering` |
| Host | Apple M1 Pro, 16 GB, macOS 27.0.1 |
| Toolchain | Python 3.12.0, uv 0.11.7, Node 22.9.0 locally (CI pins `.node-version`) |
| Network | Metro M1 and Konak Tram: 48 stops, 1,574 trips, 2 documented interchanges |
| Deterministic tests | `pytest -m "not ollama"`: 74 passed, 2 deselected |
| Coverage | 87% branch coverage across all of `trl` (the v1.2.0 gate measured four modules) |
| Demo route search | `find_offers(limit=6)` p50 386 ms, max 420 ms over 15 warm runs; 1,737 labels, 141 pairs |
| Schedule load | 0.20 s |

```sh
uv run --locked --project backend pytest backend/tests -m "not ollama" -q
uv run --locked --project backend pytest backend/tests -m "not ollama and not deep" \
  --cov --cov-config=backend/pyproject.toml --cov-report=term
```

## Reproduced defects

[`test_v2_defects.py`](../../backend/tests/test_v2_defects.py) records each defect as a strict
expected failure. A test fails on the v1.2.0 behavior, and pytest reports an error if it passes
while still marked. The fixing commit removes the marker.

| ID | Failing case | v1.2.0 behavior | Expected behavior |
| --- | --- | --- | --- |
| C1 | `closed from 08:24 to 10:00 on 14.11.2026`, `22 Ekim'de`, `next Friday`, `2030-01-01T08:24` | Applied to 2026-10-21 (the ISO form asks for a start time) | Abstain: the notice names another service date |
| C2 | `from 2026-10-21T08:24:00+03:00 to 10:00` | Closure 03:00–10:00 | Closure 08:24–10:00; `+03:00` is the local offset |
| C3 | `08:24'ten 10:00'a kadar`, `08.24 ile 10.00 arasında`, `until 10:00 from 08:24` | `unbound_times` or no times | Closure 08:24–10:00 |
| C3 | `saat 10:00'a kadar kapalı`, `closed before 10:00` | 10:00 becomes the start | 10:00 is the end |
| C4 | `from 8:24 to 10:00 pm` | 08:24–22:00 | 20:24–22:00 |
| C4 | `seferi 1,5 saat gecikmeli` | 18,000 s delay | 5,400 s delay |
| C4 | `from 23:30 to 00:30` | Rejected as an invalid event | 23:30–24:30 in service-day seconds |
| C5 | Rider alights at a stop at t=5 and boards at t=12 while the stop is closed 6–10 | Router returns the plan, verifier accepts it | Both reject waiting inside a closed stop |
| C6 | A second report replaces the first closure | Both closures remain active | The replacement retracts the earlier incident |
| C7 | `TRAM:7 is closed ...` | Target lost | Identifiers are case-insensitive |
| L1 | Initial search exhausts its budget | `SearchIncomplete` escapes as HTTP 500 | Run recorded as `search_incomplete` |
| L2 | `step(updates={"status": "bogus"})` | Persisted; later reads fail | Rejected before the write |
| L2 | Route search raises `RuntimeError` | `model_error` | `system_error` |
| L4 | Database with `user_version = 99` | Silently rewritten to 2 | Refused |
| L6 | `closed.` → answer `08:24` | Abstains after one answer | Second question for the end time |
| L7 | Verified model quote `shuttered` | Ignored unless it is one of eight phrases | Applied after verification; refused from a negated clause |
| L8 | `closed from 08:24 to 10:00 (no lifts)` | Abstains on `no` | Applies the closure |
| L8 | `Konak İskele and Karataş ... closed` | `conflicting_targets` | Both closures apply |
| L9 | Prompt file edited | Request digest unchanged | Digest changes |

The [engineering plan](engineering-plan.md) lists the remaining findings, which are covered by
phase acceptance checks rather than unit regressions: evaluation design (E1–E7), worker
ownership and streaming (L3, L5, L10) and platform gaps (P1–P7).
