# ADR 0007 · Preview alternative disruptions before applying an event

## Decision

The vNext workflow represents report fields as typed values with Unicode code-point
spans into the local report. The Operator can quote a supported indirect phrase.
The server derives field values and catalogue IDs, computes temporary timetable
previews for up to four candidate events, and chooses one clarification slot.
Selection minimizes the worst remaining feasibility disagreement and meeting-time
spread. The original report and the current clarification define the evidence.

The command transaction binds a question and its answer to the run revision.
It applies the first valid command once. An unresolved answer is a terminal
outcome. Run state and public events live in SQLite. LangGraph checkpoints store
execution position. A pending inference reservation consumes the vNext message's
single attempt after restart.

## Route evidence

The bounded route search retains up to eight distinct chains per nominal ranking.
The simulator evaluates the union using the same 128 synthetic delay worlds.
It groups equivalent per-offer delay assignments before verification. The
published results describe this candidate pool and this perturbation profile.

The nominal verifier reads the timetable directly, checks the complete joint
plan, and requires two distinct accepted votes on the same offer and revision.
Preview outcomes, simulated reliability counts, and nominal verification have
separate meanings and separate UI labels.

## Compatibility

Legacy requests retain their original workflow, stored fields, idempotency
fingerprints, and event contract. New evidence is optional on the read model.
Use the pre-upgrade SQLite backup for rollback to a release that predates the
vNext records.
