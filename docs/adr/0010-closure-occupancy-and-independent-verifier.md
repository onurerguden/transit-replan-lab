# ADR 0010 · Forbid presence in closed stops and verify with independent semantics

Date 2026-11-13 · Accepted

## Context

The router checked a stop closure only at boarding and alighting instants. A rider could alight
before a closure, wait through it and board afterwards. The verifier used the router's overlay
methods, so it inherited the same blind spot. Its independence from routing held only at the
import level.

## Decision

- Presence in a closed stop is forbidden at every second. [Closure semantics](../semantics/closures.md) lists the presence intervals.
- The router prunes departures that require waiting through a closure and bounds the wait before a walk.
- `trl.verifier` is a separate package. It re-derives presence intervals from a finished plan and interprets disruptions with its own `IncidentState`. It imports neither routing, the overlay, robustness nor the legacy `trl.verify` adapter. Import contracts enforce this.
- `trl.verify` stays as an adapter that copies compiled incident data into `IncidentState` and delegates, so existing callers keep their signatures.
- An exhausted initial search is stored as a `search_incomplete` run instead of failing run creation.
- A frozen copy of the label search is kept under `backend/tests` as the differential target for routing v2.

## Consequences

The verifier returns `closed_dwell` for waiting through a closure. Hypothesis compares the router and verifier with an exhaustive journey oracle over networks with mid-trip boarding, pickup and drop-off flags, closures, cancellations, delays and wait limits. The demo output matches v1.2.0 byte for byte.
