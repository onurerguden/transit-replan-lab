# Roadmap

The current phase is **1 · Domain and schedule**. Run `make check` and review the checklist before each phase commit.

## 0 · Foundation

- [x] Bootstrap a standalone Git repository, locked Python and frontend dependencies, and a CI workflow.
- [x] Run the full check and build workflow locally.
- [x] Prove the publication checks catch an injected term in the index, a message, and history.
- [x] Verify model, graph APIs, feed licensing, and transfer claims in ADRs.
- [x] Validate a real local structured response and record the model digest.
- [x] Confirm the Git author email and obtain maintainer approval for the phase commit.

The Phase 0 workflow passed on macOS and in an Ubuntu container via act. The maintainer approved the phased implementation and release.

## 1 · Domain and schedule

- [ ] Add domain types, fetch and checksum verification, and pinned feed provenance.
- [ ] Load Metro M1 and Konak Tram including service calendars, exceptions, 24+ hour times, and pickup/drop-off.
- [ ] Document two interchange links, walking assumptions, and a fixed service date.
- [ ] Test genuine feeds and checksum mismatch.

## 2 · Routing and verification

- [ ] Implement connection scanning with multiple arrival labels, joint arrival ranking, and versioned incident overlays.
- [ ] Verify itinerary legs and hard constraints independently, and prohibit imports from the router.
- [ ] Compare random small networks against exhaustive enumeration. Reject mutated journeys and cover midnight, later arrivals, closures, and accessibility.
- [ ] Freeze and run the real timetable demo through the CLI.

## 3 · Service and persistence

- [ ] Add SQLite WAL migrations, repositories, and the rules-based graph with persistent checkpoints.
- [ ] Implement versioned idempotent commands, RFC 9457 errors, and event replay with Last-Event-ID.
- [ ] Verify model-free replanning, conflicting commands, restart recovery, and SSE resume. Generate OpenAPI.

## 4 · Simulation interface

- [ ] Show offline before and after maps, closure markers, offer focus, role actions, and an accessible timeline.
- [ ] Generate client types from OpenAPI and keep proposals visually distinct from verified plans.
- [ ] Verify keyboard navigation, reconnect consistency, and the model-free browser path.

## 5 · Agent variants

- [ ] Implement the Ollama and replay model ports, isolated role views, and structured role outputs.
- [ ] Support rules-based, single-, three-, and five-agent graphs with a bounded offer and vote protocol.
- [ ] Test role permissions, call and round limits, clarification, and real-model feasible and infeasible cases.

## 6 · Reliability and observability

- [ ] Exercise process interruption, late responses, duplicate incidents, and obsolete votes.
- [ ] Add trace hierarchy, JSON logs, per-call measurements, and an optional local trace viewer.
- [ ] Validate that an invalid plan can never receive a verified state.

## 7 · Comparative experiment

- [ ] Commit the protocol before results, with 24 development and 60 locked scenarios and a counteroffer ablation.
- [ ] Run a resumable benchmark with fixed inputs, per-row provenance, and paired bootstrap intervals.
- [ ] Use development evidence for the default, evaluate the locked partition, and publish measured metrics.

## 8 · Operator LoRA

- [ ] Generate split-isolated bilingual data and document the data card.
- [ ] Run an Apple silicon MLX pilot and training, then compare base and adapter in the same runtime.
- [ ] Apply the development adoption threshold, evaluate the held-out split, and rerun the relevant routing experiment slice.
- [ ] Verify the Ollama deployment path and document the adoption decision.

## 9 · Packaging and release

- [ ] Validate Docker and local setup from a clean checkout and run model-free browser CI.
- [ ] Publish a project README with screenshots, reproduction commands, outcomes, attribution, and limitations.
- [ ] Review candidate files, complete history, prompts, data, and secret scans with the maintainer.
- [ ] Create and push the public repository after approval and tag v1.0.0.
