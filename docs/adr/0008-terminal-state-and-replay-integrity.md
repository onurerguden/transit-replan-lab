# 0008. Own execution per revision and validate durable model replies

Accepted for local macOS and Linux deployments.

Multiple API processes can open the same SQLite database. LangGraph checkpoints
and application events commit separately. A revision check allows two processes
to advance the same checkpoint or a late result to change a terminal run.

Acquire an advisory file lock scoped to the resolved database path, run ID
and revision before invoking the graph. A contender checks the current state
between waits and retries while the revision is planning. This covers an answer
arriving while the previous worker persists the interrupt. Process exit releases
the lock. Retain lock files while the database is in service so contenders lock
the same inode. Put the database and lock directory on the same local writable
volume. Cross-host workers require a different ownership mechanism.

Application steps, model reservations and model completions check the revision
and planning status in their write transaction. A new disruption can open a
new revision. A pending attempt remains charged after a crash. Model I/O stays
outside SQLite transactions.

Replay valid replies whose request digest matches the versioned role view.
An active legacy revision with a missing digest reports a request mismatch.
Submitting a fresh disruption opens a new revision. Completed historical
outcomes stay readable. Prompt revisions form part of the request digest.
A committed reply retains its recorded model identity on replay.
