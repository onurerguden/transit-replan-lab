# Roadmap

The v1 implementation and verification checklist is complete. See the [v1.0.0 release](https://github.com/onurerguden/transit-replan-lab/releases/tag/v1.0.0) for the tagged snapshot.

## 0 · Foundation

- [x] Bootstrap a standalone Git repository, locked Python and frontend dependencies, and a CI workflow.
- [x] Run the full check and build workflow locally.
- [x] Prove the publication checks catch an injected term in the index, a message, and history.
- [x] Verify model, graph APIs, feed licensing, and transfer claims in ADRs.
- [x] Validate a real local structured response and record the model digest.
- [x] Confirm the Git author email and obtain maintainer approval for the phase commit.

The Phase 0 workflow passed on macOS and in an Ubuntu container via act. The maintainer approved the phased implementation and release.

## 1 · Domain and schedule

- [x] Add domain types, fetch and checksum verification, and pinned feed provenance.
- [x] Load Metro M1 and Konak Tram including service calendars, exceptions, 24+ hour times, and pickup/drop-off.
- [x] Document two interchange links, walking assumptions, and a fixed service date.
- [x] Test genuine feeds and checksum mismatch.

## 2 · Routing and verification

- [x] Implement connection scanning with multiple arrival labels, joint arrival ranking, and versioned incident overlays.
- [x] Verify itinerary legs and hard constraints independently, and prohibit imports from the router.
- [x] Compare random small networks against exhaustive enumeration. Reject mutated journeys and cover midnight, later arrivals, closures, and accessibility.
- [x] Freeze and run the real timetable demo through the CLI.

## 3 · Service and persistence

- [x] Add SQLite WAL migrations, repositories, and the rules-based graph with persistent checkpoints.
- [x] Implement versioned idempotent commands, RFC 9457 errors, and event replay with Last-Event-ID.
- [x] Verify model-free replanning, conflicting commands, restart recovery, and SSE resume. Generate OpenAPI.

## 4 · Simulation interface

- [x] Show offline before and after maps, closure markers, offer focus, role actions, and an accessible timeline.
- [x] Generate client types from OpenAPI and keep proposals visually distinct from verified plans.
- [x] Verify keyboard navigation, reconnect consistency, and the model-free browser path.

## 5 · Agent variants

- [x] Implement the Ollama and replay model ports, isolated role views, and structured role outputs.
- [x] Support rules-based, single-, three-, and five-agent graphs with a bounded offer and vote protocol.
- [x] Test role permissions, call and round limits, clarification, and real-model feasible and infeasible cases.

## 6 · Reliability and observability

- [x] Exercise process interruption, late responses, duplicate incidents, and obsolete votes.
- [x] Add trace hierarchy, JSON logs, per-call measurements, and an optional local trace viewer.
- [x] Validate that an invalid plan can never receive a verified state.

## 7 · Comparative experiment

- [x] Commit the protocol before results, with 24 development and 60 locked scenarios and a counteroffer ablation.
- [x] Run a resumable benchmark with fixed inputs, per-row provenance, and paired bootstrap intervals.
- [x] Use development evidence for the default, evaluate the locked partition, and publish measured metrics.

## 8 · Operator LoRA

- [x] Generate split-isolated bilingual data and document the data card.
- [x] Run an Apple silicon MLX pilot and training, then compare base and adapter in the same runtime.
- [x] Apply the development adoption threshold, evaluate the held-out split, and rerun the relevant routing experiment slice.
- [x] Verify the Ollama deployment path and document the adoption decision.

## 9 · Packaging and release

- [x] Validate Docker and local setup from a clean checkout and run model-free browser CI.
- [x] Publish a project README with screenshots, reproduction commands, outcomes, attribution, and limitations.
- [x] Review candidate files, complete history, prompts, data, and secret scans with the maintainer.
- [x] Publish the public repository and tag the release after CI.

## Review follow-up

The [implementation record](review-implementation.md) covers durability,
operator comparisons, the refreshed interface and local package acceptance.
The [evaluation protocol](review-evaluation-protocol.md) records the remaining
independent holdout work.

## v2

The [v2 engineering plan](v2/engineering-plan.md) extends the scope to the full İzmir network.
The [baseline](v2/baseline.md) lists the reproduced defects, and the
[implementation log](v2/implementation-log.md) records progress.

- [x] F0 · Record the baseline and strict expected failures, centralize settings and versions, widen lint and coverage, split and pin CI.
- [x] F1 · Specify closure occupancy, give the verifier its own reference timetable and semantics, and record exhausted initial searches.
- [x] F2 · Add numbered migrations, a transition table, incident sets, leases with fencing, pruned checkpoints, notifier SSE and multi-round clarification.
- [x] F3 · Pin all five feeds with health checks, generate footpaths, build the gazetteer and add network profiles.
- [x] F4 · Freeze the sealed TRL-Bench v3 notice layer before any language change.
- [x] F5 · Replace the time grammar and evidence gate, with round-trip and gate-soundness property suites.
- [x] F6 · Ship the compact timetable, the bounded and fast searches, differential tests, budgets and load measurements.
- [x] F7 · Sample scenarios, require two-router label agreement, and build the resumable evaluation harness and preregistration.
- [x] F8 · Train Operator LoRA v2 and run the single final evaluation.
- [x] F9 · Deliver addressable runs, the incident and clarification interface, bilingual UI and accessibility tests.
- [x] F10 · Add metrics, tracing, readiness, security headers, rate limiting and supply-chain scanning.
- [x] F11 · Publish documentation and prepare the signed release workflow.
