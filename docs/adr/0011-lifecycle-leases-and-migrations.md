# ADR 0011 · Table-driven lifecycle, execution leases and numbered migrations

Date 2026-11-13 · Accepted · Supersedes the file-lock ownership in [ADR 0008](0008-terminal-state-and-replay-integrity.md).

## Context

Statuses were string literals scattered through the worker, the store applied free-form
updates without validation, and any failure became a terminal `model_error`. Ownership of a
revision used a per-run advisory file lock that contenders polled every 100 ms, only worked on
a local filesystem and could not tell a stale writer from a live one. The schema version was
written before the migration ran and never read. Corrections could not remove an earlier
incident because overlays only accumulated.

## Decision

- `trl.lifecycle` holds the status set, the statuses each command may start from, and what a
  worker may write while a run is planning. The store validates every worker update against
  `RunBody` and the table, and turns a violation into a `Conflict`.
- `system_error` separates internal failures from `model_error`. A failure code tells the
  client whether the run is `retryable`. The `retry` command opens a new revision.
- Incident sets are explicit. `Disrupt` takes `mode: add | replace`, `Retract` removes
  incidents by identifier, and both open a new revision. Retracting the last incident returns
  the run to `ready`. A retracted revision skips report intake.
- A `leases` table replaces the file lock. A worker takes the lease for a run revision,
  heartbeats at a quarter of the TTL, and every guarded write checks its fencing token in the
  same transaction. Any command moves the token on, so a worker started before the command
  cannot write after it. A newer revision also cancels the older local task.
- Execution checkpoints live in `<database>.checkpoints.sqlite`. A settled revision deletes
  its thread, and startup deletes threads of settled or superseded revisions.
- Migrations are numbered. `PRAGMA user_version` is read first, a populated database is backed
  up with the SQLite backup API, each migration runs in its own `BEGIN IMMEDIATE` transaction
  with the version bump, integrity and foreign key checks follow, and a database from a newer
  release is refused. Version 2 is the v1.2.0 schema. Version 3 adds leases, moves checkpoints
  out and marks runs that were planning during the upgrade as `system_error` with the
  retryable code `upgrade_interrupted`.
- Clarification continues for up to three rounds. An unreadable answer asks the same question
  again, and a refusal or unsupported context ends the run as abstained.
- `trl db` provides `migrate`, `check`, `backup`, `restore` and `prune`. Restore verifies the
  manifest checksum, refuses a newer schema or a live lease, then migrates forward.

## Consequences

Takeover after a crash waits for the lease to expire (`TRL_LEASE_TTL`, 20 s by default),
where the file lock released immediately. Contenders poll with a bounded backoff rather than a
dispatcher. The lease is host-local like the database. A state machine test drives the public
store API with restarts, replays, conflicts and stale writers against fourteen invariants.
