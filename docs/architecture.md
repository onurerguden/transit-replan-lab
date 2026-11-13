# Architecture

```mermaid
flowchart LR
  UI[React and MapLibre] -->|REST and SSE| API[FastAPI]
  API --> SERVICE[Run service]
  SERVICE --> STATE[(SQLite run state and events)]
  SERVICE --> GRAPH[LangGraph]
  GRAPH --> CP[(Execution checkpoints)]
  GRAPH --> ROLES[Isolated role views and model port]
  GRAPH --> ROUTING[Route search]
  GRAPH --> VERIFY[Independent verifier]
  ROUTING --> DATA[Frozen GTFS and incident overlays]
  VERIFY --> DATA
  GRAPH -.-> OTEL[OpenTelemetry]
```

The application owns the current incident version, offers, votes, and status. The graph checkpoint owns execution position. A new incident uses a new thread keyed by run and version. On resume, a node can reuse its committed step by key. A write checks the incident version inside the same SQLite transaction as the corresponding public event. Model calls run outside that transaction.

The router and independent verifier both read the same schedule and incident types. The verifier reconstructs trip legs from the schedule without importing the router. Verification also requires one acceptance per rider for the same current-version offer. Agents receive role-specific projections of state.

Only the worker holding the local lock advances a revision checkpoint. Application writes require the revision to be planning. Cached model decisions are bound to the versioned role view. See the [execution and replay decision](adr/0008-terminal-state-and-replay-integrity.md).

## Incident and route evidence

The Operator proposes a typed incident. The application compares its fields with the explicit event supported by the notice before it changes the timetable. An ambiguous or conflicting notice produces a clarification. For terminal walks, the route engine intersects feasible arrival windows with the rider wait limits. The independent verifier checks the resulting timestamps against the schedule. [Decision record](adr/0006-incident-evidence-and-walking-windows.md).

## Interface direction

The simulation opens with the disruption, selected offer and verification evidence. Clarification controls precede the paired maps. Both maps use a common extent, transfer symbols and matching stop labels. A compact journey comparison under the maps gives arrival and waiting times. The timeline sits alongside the maps on wide screens and follows them on narrow screens. Clicking an offer highlights its exact legs and retains keyboard focus on the offer. The evidence inspector shows the selected revision, trip IDs and dates, rider votes, destination waits, and the verifier's result. Verification state is written out beside an icon, and a closed stop has a distinct map marker. The map and fonts must work offline.

A dropped command response can be retried with its original request body and idempotency key. The browser streams the activity and reads the outcome when the current revision reaches a terminal event. A failed outcome read has its own retry without an additional mutation.

## Inspect a run

Start Jaeger with `docker compose --profile obs up -d jaeger`. Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` for the local API. Find service `transit-replan-lab` in the [Jaeger UI](http://localhost:16686). The local smoke test observed 15 spans for the mediated demo, including seven model spans parented by graph nodes. The JSON run log carries the matching run and trace IDs. The SQLite ledger records reserved attempts, model digest, context, token counts, duration, and schema outcome. Prompts and user notices are excluded from span attributes.

Run the browser and persistence tests with `make check` and `make e2e`. In fault tests, a process is killed after a durable graph node and again during a reserved model call. The resumed work spends another reserved call in the latter case. A late result for a superseded version changes no application data.
