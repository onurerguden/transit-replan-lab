# Changelog

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[semantic versioning](https://semver.org/).

## [Unreleased]

### Added

- TRL-Bench v3.1 (`data/bench/v31`, `experiments/bench_v31`): split-owned sentence frames, 3,859 distinct train templates, test wording from a model of another family, a phrase-level audit and a gold-quote check by family.
- An Ollama evaluator (`finetune/v3_evaluate.py`) with parallel requests, and a retrieval arm (`finetune/rag.py`) over the train bank.
- Operator adapter v3 trained on v3.1 (three seeds), ADR 0017 and a preregistered comparison with the lexicon, the base model and retrieval.
- MinHash near-duplicate removal and wording-overlap measures (`experiments/bench_v3/overlap.py`).

### Fixed

- The schema sent to Ollama now requires the event `kind` of a quote. Before, constrained decoding skipped it and the evidence gate ignored every model quote.
- A numeric date followed by a label colon (`17.11.2026:`) is now read, so a notice for another day is no longer applied to the service day.

## [2.0.0] - 2026-11-14

### Added

- Five official İzmir feeds (Metro, every tram line, İZBAN, ESHOT, İzdeniz) described in `feeds.json`, with a committed health report, labelled calendar projections and generated footpaths. İzdeniz is recorded as unavailable because its URL returns a web page.
- `POST /v1/route`, a stateless meeting query on the core or the full network. A fast mode that dominates across arrival times removes the incomplete outcomes on the full network benchmark and keeps the best offer. Exact mode keeps every alternative chain and can end as incomplete.
- A compiled network (`trl.timetable`) with a cache, a bounded query and a deterministic work budget, measured on the full network.
- An independent verifier package with its own incident semantics and presence intervals.
- A transition table, `system_error`, a retry command, add, replace and retract commands for incidents, up to three clarification rounds, numbered migrations with backup, and `trl db` for backup, restore, check and prune.
- Execution leases with fencing tokens, notifier-driven event streams, a separate pruned checkpoint database and RFC 9457 problem details everywhere.
- A shared time grammar for Turkish and English reports, clause-scoped negation, case-insensitive identifiers, conjoined stops, trips named by a stop and a departure time, and a verified-quote evidence gate.
- TRL-Bench v3: 4,900 generated groups in four disjoint splits with an audit, a freeze manifest, a preregistration, cluster statistics and a paraphrased test set from a second model family.
- Prometheus metrics, readiness, rate limiting, security headers, a Grafana dashboard, CodeQL, dependency scans and a release workflow with signed images.
- Interface: runs reopen from a link, active disruptions with a retract button, retry, English and Turkish, light and dark themes and an accessibility check.

### Changed

- A rider can no longer wait inside a closed stop, in the router or in the verifier.
- A report for another day, a relative day or another time zone is no longer applied to the service day.
- A model's event quote is accepted only when the text supports it, instead of only when it equals one of eight phrases.
- Environment variables are read through one validated settings class, and the API is built by a factory (`uvicorn --factory trl.api.app:create_app`).
- Execution checkpoints moved to `<database>.checkpoints.sqlite`. Runs that were planning during the upgrade become retryable `system_error` runs.

### Fixed

- 27 reproduced defects with regression tests: ISO offsets read as clock times, Turkish suffix and range binding, meridiem and decimal-comma handling, overnight ranges, uppercase identifiers, global negation, accumulating incidents, an HTTP 500 on an exhausted search, invalid statuses reaching the database, a schema downgrade, and prompt edits that did not change the request digest.

## [1.2.0] - 2026-11-13

Evidence review: durability, operator comparison with a lexicon arm, a refreshed interface and a synthetic holdout.

## [1.1.0] - 2026-11-12

Evidence-led replanning: typed incidents grounded in the report, previews of competing readings, resilience over delay worlds and an Operator adapter experiment.

## [1.0.0] - 2026-11-12

First release: Metro M1 and Konak Tram, four coordination variants, independent verification, local inference and a reproducible comparison.
