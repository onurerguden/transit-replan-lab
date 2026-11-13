# ADR 0014 · Compile the network once and bound each query before searching

Date 2026-11-14 · Accepted

## Context

The label search keeps a label for every arrival second at every stop. That is exact and fast on
the 48-stop core network, but the five-feed network has 11,857 stops and 2.2 million stop times,
so building and scanning it as objects costs minutes and gigabytes.

## Decision

- `trl.timetable.compact` compiles every archive into numpy arrays and caches them under a key
  of the archive checksums, feed metadata, transfers and compiler version. Compiling the full
  network takes about five seconds and loading the cache takes about 30 ms.
- `trl.timetable.query` bounds a query with two vectorized passes. A forward pass gives the
  earliest each rider can reach every stop and a backward pass gives the latest they can leave a
  stop and still reach a destination. Both ignore closures, cancellations and accessibility,
  which only remove options, and apply delays, which can add some. Trips that cannot lie on any
  journey are dropped and the exact search runs on what remains.
- Meetings are searched in growing horizons past the lower bound. Offers rank by meeting time
  first, so a horizon that already yields `limit` offers contains the answer for the whole window.
- `routing.Budget` counts every candidate label and examined pair and optionally checks a
  deadline. Exhaustion is an explicit `SearchIncomplete`.
- Differential tests compare the bounded search with the full search on random core scenarios
  with closures, a delay and several seeds. They agree exactly.

## Measured result

On the 2026-10-21 weekday with riders starting near a shared destination (40 queries, two
repeats, one and four processes, Apple M1 Pro): load and footpath generation in 0.3 s, 152 MB
after load, 513 MB peak. One process gave p50 1.56 s and p95 3.6 s. Four processes gave 2.3
queries per second. Of 40 queries, 13 were feasible, 14 infeasible and 13 ended as an explicit
incomplete outcome after the work budget. No emitted offer failed the verifier. The target of
a p95 under 1.5 s and no incomplete outcomes was not met. Dense bus meetings with generated
walking links still expand too many labels for the exact search.

## Consequences

The API still runs on the core schedule. The full network is available through the library and
the benchmark script, and its plans are checked by `trl.verifier.sqlite_reference`, which reads
the raw archives instead of the compiled arrays. Closing the gap needs dominance across arrival times
(range RAPTOR) instead of a label per second, which this release does not implement.
