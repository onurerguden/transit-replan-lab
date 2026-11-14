# Closure semantics

Both the router and the verifier implement this specification independently. The router
(`trl.routing`) searches with it. The verifier (`trl.verifier`) re-derives presence intervals
from a finished plan and shares no code with the router or its overlay.

## Definitions

- Times are service-day seconds and may exceed 86,400.
- A closure of stop `s` is the half-open interval `[from, until)`. A stop is closed at `t` when
  `from <= t < until`.
- A rider is **present** at a stop over a closed interval `[first, last]` of seconds.

## Occupancy rule

A rider may not be present at a stop at any second it is closed. Presence intervals are:

| Situation | Stop | Interval |
| --- | --- | --- |
| Waiting at the origin or after alighting | the stop | from arrival (or readiness) to the next departure |
| Alighting | the stop | the arrival second |
| Walking | both walk endpoints | from walk departure to walk arrival |
| Waiting for the meeting | the destination | from the rider's arrival to the meeting |

Riding through a stop without alighting is not presence. A closed stop never forbids a vehicle
from passing through.

## Consequences

- Boarding at a closed second is rejected (`closed_platform`).
- Waiting through a closure between an arrival and a later departure is rejected
  (`closed_dwell`), even when both instants are open.
- A walk is rejected when either endpoint is closed during the walk (`closed_transfer`).
- Waiting at the destination through a closure is rejected (`closed_destination`).

## Incidents

- Delays add to the scheduled call times of one trip occurrence. Several delays on one
  occurrence add up in the verifier.
- A cancelled occurrence cannot be boarded.
- Offsets for overnight service shift calls by whole days.
