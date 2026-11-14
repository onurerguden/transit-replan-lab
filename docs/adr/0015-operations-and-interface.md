# ADR 0015 · Measure the service, protect its edges and make runs addressable

Date 2026-11-14 · Accepted

## Decision

- The tracer provider is registered globally and flushed at shutdown. FastAPI requests are traced when an OTLP endpoint is set, so a request, its worker, its model calls and its search share one trace.
- Prometheus metrics at `/metrics` cover requests and latency by route, run outcomes, model call duration, route-search work units, incomplete searches, open event streams, fenced writes and rate-limited requests. A provisioned Grafana dashboard and a Prometheus scrape job ship in the `obs` Compose profile.
- `/readyz` checks the database at the current schema and the loaded timetable. `/healthz` stays a liveness check. The Compose health check uses readiness.
- A token bucket limits POST requests per client (`TRL_RATE_LIMIT`, 600 per minute by default, zero disables it). A refusal is a problem response with `Retry-After`.
- nginx and the API send security headers, including a content security policy that still allows the offline map workers. Metrics and readiness are not exposed through the public proxy.
- CodeQL, dependency audits for Python and the frontend, and a Trivy scan run in separate workflows with actions pinned by commit.
- The interface reopens a run from `?run=<id>`, lists active disruptions with a retract button, offers a retry for retryable failures, copies a link, switches between English and Turkish and between light and dark themes, and passes an axe check in both themes. The language switch covers status labels and the new controls, not every sentence.

## Consequences

There is no authentication, so a run identifier is the only access control and the rate limit is per address, not per user. Traces from another process join only through the exported endpoint.
