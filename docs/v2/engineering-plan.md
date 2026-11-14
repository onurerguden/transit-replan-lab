# v2.0 engineering plan

v1.2.0 is a disciplined prototype. It separates routing from verification, makes commands
idempotent, tests routing against an exhaustive oracle and records provenance. The review that
precedes this plan found four structural limits:

1. The network covers 48 stops and 1,574 trips.
2. The evaluation sets are small and were designed alongside the system, so several arms reach
   100% by construction.
3. The Turkish and English time grammar can apply the wrong event, and the run can still reach
   a verified state.
4. Run lifecycle transitions are untyped, and worker ownership is single-host.

v2.0.0 addresses these limits with measured claims. The [baseline](baseline.md) records the
starting point and the reproduced defects.

## Scope decisions

| Decision | Choice |
| --- | --- |
| Network | All five official İzmir GTFS feeds: Metro, every tram line, İZBAN, İzdeniz and ESHOT. The demo keeps Metro M1 and Konak Tram as the `core` profile. |
| Human annotation | None available. Benchmarks use synthetic text and external-family paraphrases. A blind review packet stays ready for future reviewers. |
| Demo | Local Docker only. Steps that need an external account or API key, such as a hosted deployment or licensed real alert feeds, are out of scope. |
| Model training | Operator LoRA v2 trained locally with MLX. |
| Version | 2.0.0, because the scope, API and schema change. |

## Findings

**Correctness.**
- C1: notices for other dates apply to the service date.
- C2: an ISO offset is read as a clock time.
- C3: Turkish suffixes and English prepositions bind times to the wrong role.
- C4: meridiem, decimal-comma durations and overnight ranges are mishandled.
- C5: router and verifier both allow waiting inside a closed stop.
- C6: incidents accumulate across revisions.
- C7: identifiers are case-sensitive.

**Lifecycle and performance.**
- L1: the search budget bounds neither work nor time, and an exhausted initial search returns HTTP 500.
- L2: transitions are untyped, and every failure is reported as a model error.
- L3: superseded tasks are not cancelled, and ownership uses a spinning file lock.
- L4: migrations do not read the schema version, and checkpoints are never pruned.
- L5: synchronous SQLite runs on the event loop, SSE polls the database per client, and the stream closes at clarification.
- L6: clarification has one round.
- L7: the evidence gate accepts only eight fixed phrases from a model.
- L8: any negation anywhere abstains, there are no multi-event notices, and trip events need raw GTFS IDs.
- L9: prompt content is not part of the request digest.
- L10: nothing is cached.

**Evaluation.**
- E1: the benchmark and the phrase whitelist were written together.
- E2: the effective sample is 16 templates, 3 stops and one rider pair per split.
- E3: ceiling effects, point-estimate gates, and a memorized adapter.
- E4: template leakage across splits and into training.
- E5: the bootstrap ignores template clusters.
- E6: infeasibility labels come from the router under test.
- E7: the runner cannot resume.

**Platform.**
- P1: runs are not addressable by URL.
- P2: no security scanning or release automation.
- P3: version drift.
- P4: shallow observability.
- P5: partial coverage gate.
- P6: thin frontend tests.
- P7: scattered configuration.

## Target architecture

New code lands in packages; existing modules remain thin façades so public signatures stay
stable.

```
backend/src/trl/
  settings.py lifecycle.py errors.py feeds.py raptor.py pairing.py
  timetable/    compile.py compact.py cache.py footpaths.py profiles.py
  verifier/     reference.py occupancy.py check.py
  language/     normalize.py timeexpr.py dates.py clauses.py events.py targets.py gazetteer.py gate.py
  migrations/   runner.py and numbered migrations
  persistence/  leases.py backup.py async_store.py
  api/          app.py problems.py sse.py ratelimit.py
data/lexicon/{tr,en}.yaml
data/bench/v3/{phrases,sealed,frames,manifests}/
```

Import contracts:
- The verifier imports none of routing, RAPTOR, pairing, the compiled timetable or the router's overlay.
- Routing never imports the verifier.
- The language layer never imports routing.

## Phases

Each phase ends with `make check`, a roadmap checkbox, an implementation log entry, the
relevant ADR and Conventional Commits. A phase also removes the strict expected-failure markers
for the defects it fixes.

| Phase | Work | Acceptance |
| --- | --- | --- |
| F0 Baseline and guardrails | Branch, baseline, strict expected failures for each defect, one settings class, one version source, wider lint rules with a phase-tagged ratchet, branch coverage across `trl`, hermetic `make test`, `make test-ollama`, `make test-deep`, split and pinned CI, OpenAPI drift check, Dependabot, ADR 0009 | Existing checks green; every defect test reports an expected failure |
| F1 Closure semantics and independent verifier | Occupancy rule in `docs/semantics/closures.md`, dwell check in the legacy search, a frozen oracle copy, a `trl.verifier` package with its own reference timetable and presence intervals, a recorded `search_incomplete` initial search, extended exhaustive oracles, ADR 0010 | C5 and L1 pass; the oracle suites pass at 500 examples in CI and 10,000 nightly; demo output unchanged |
| F2 Lifecycle and persistence | v1.2.0 fixture database; numbered migrations with backup and integrity checks; transition table, typed commands and events, `system_error`, error taxonomy; incident sets with add, replace and retract; leases with fencing tokens; separate pruned checkpoint database; async store; notifier-based SSE; up to three clarification rounds; database CLI; problem details everywhere; stateful property test and crash matrix; ADR 0011 | The fixture upgrades with identical views, events and receipts; a completed revision stays readable after restart and backup restore; the state machine passes 100×30 in CI and 2,000 nightly |
| F3 Feeds and catalogue | Feed health (magic bytes, checksum, calendar coverage), optional feeds, labelled calendar policy, frequency expansion, invalid-trip quarantine; all five archives pinned with license and checksum; generated footpaths with labelled parameters and transitive closure; a gazetteer with Turkish suffix stripping; `core` and `full` profiles; ADR 0013 | Feed health report committed; counts recorded; triangle-inequality property holds; `core` results unchanged |
| F4 Sealed benchmark notice layer | Event frames, compositional realization with Turkish morphology, noise, natural-language answers, delexicalized paraphrases from a different model family with a second-family judge, held-out stops and constructions, freeze manifest A. All of this happens before any language change. | Audit passes: disjoint templates and phrase IDs, zero n-gram overlap between the production lexicon or prompts and the test bank, held-out stops absent from train and dev |
| F5 Language layer and evidence gate v2 | Shared time and date grammar with role binding, clause-scoped negation and hedging, YAML lexicon from the development bank, conjunction and disjunction, natural-language trip references, a gate that verifies model quotes against deterministic parsers, prompt content in the digest; round-trip and gate-soundness property suites; ADR 0012 | C1–C4, C7 and L6–L9 pass; zero unsupported applications in at least 20,000 adversarial cases |
| F6 Routing v2 and load | Compact numpy timetable with a checksum-keyed cache, segment-scoped McRAPTOR with arrival profiles, two-pointer meeting pairing, a deterministic work meter and deadline, sound pruning, an independent SQLite reference for the verifier, distinct resilience worlds with intervals, a workload harness with baseline repeats and a work-unit CI gate; ADR 0014 | Equal feasibility and rank tuples against the oracle and the legacy search; every offer verifies; full-network RSS below 400 MB and warm p95 below 1 s (1.5 s acceptance) on 200 sampled scenarios |
| F7 Scenario layer and evaluation harness | Stratified rider and incident sampling; an independent reference router whose agreement is required for plan labels; freeze manifest B and data card; resumable parallel runner with a request-digest cache; separated metrics; two-level cluster bootstrap, exact McNemar, Holm and Clopper–Pearson; a preregistration committed before calibration or test inference | Audit green, 100% router agreement, preregistration precedes evaluation rows |
| F8 Operator LoRA v2 and final evaluation | Training data from the train bank only, MinHash deduplication, three MLX seeds with Ollama stopped, an adoption gate on the interval lower bound, one final run on the sealed test split; ADR 0016 | The report includes paired group-level differences, uncertainty, unsupported applications, abstention, model errors, latency and failure slices |
| F9 Frontend v2 | Addressable runs, component split, typed client, incident list with retract, multi-round clarification, retry, span highlighting, assumption labels, full-network map with clustering, Turkish and English, light and dark themes, benchmark explorer, unit and accessibility tests, additional browsers | Lint, types, unit, end-to-end and accessibility checks pass; the 320 px keyboard flow passes |
| F10 Observability and supply chain | Global tracer provider, HTTP and client instrumentation, Prometheus metrics, readiness endpoint, Grafana and Jaeger profile, security headers, rate limiting, CodeQL, dependency and image scanning, gitleaks, SBOM | One trace spans HTTP, worker, model and route; security jobs green or exceptions documented |
| F11 Documentation and release | Version 2.0.0, changelog, README, technical report, ADRs 0009–0017, a release workflow that builds signed multi-architecture images with provenance through the repository token | Clean-checkout reproduction and a release dry run |

## Benchmark scale

| Dimension | v1.2.0 | TRL-Bench v3 |
| --- | --- | --- |
| Groups (Turkish and English pairs) | 40 / 30 / 60 plus 12 holdout | train 3,000 · dev 600 · calibration 300 · test 1,000 |
| Templates | 16 masked | at least 50 constructions, plus external-family paraphrases |
| Stops | 3 | at least 40 per split; 20% of test stops held out |
| Rider pairs | 1 | at least 200, stratified by mode and distance |
| Clarification answers | gold identifiers | natural language, multiple rounds |
| Plan labels | the router under test | agreement between two independent routers plus the verifier |

The test size follows from n ≈ [z₀.₉₇₅√p_d + z₀.₈√(p_d − Δ²)]² / Δ² with p_d = 0.10 and Δ = 3
percentage points. That gives about 870 groups, or about 1,040 with a design effect of 1.2 for
the language pairs.

## Delivery

**Critical path:** F0 → F1 → F3 → F4 → F5 → F6 → F7 → F8 → F11.

**Cut order if time runs short:**
1. LoRA retraining
2. İZBAN and İzdeniz
3. Margin-aware bags on the full network
4. Extended trip references
5. Process pool
6. Restore CLI

**Never cut:** F1; migrations, fencing and the state machine; the time-grammar fixes;
gate soundness; the leakage audit and the freeze manifests.

**Out of scope:** any step that needs an external account or API key, including a hosted
deployment and licensed real alert feeds.
