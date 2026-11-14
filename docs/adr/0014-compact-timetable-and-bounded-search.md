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

## Fast mode

An opt-in `fast` mode drops a label at a non-destination stop when an earlier or equal label with
no more rides, no more walking and the same walk state already reached that stop. Waiting at an
open stop is free, so anything the dropped label could do the kept one can do. Destinations keep
every arrival because a meeting needs a rider to arrive late enough to wait for the other. The
mode is skipped when a closure exists, because waiting inside a closed stop is not allowed.
A label is dropped only after `alternatives` earlier labels that end on different trips already
cover it. With one alternative the best offer's rank (meeting, rides, walks) matches the exact
search, which differential tests check on random core scenarios. With three alternatives the
whole top six matches in every one of 39 random core scenarios at 62% of the exact work (one
alternative matches in 36 of 39 at 24% of the work). Exact mode stays available (`exact: true`).

## Measured result

On the 2026-10-21 weekday, with riders starting near a shared destination (40 queries, two repeats,
Apple M1 Pro), the network loads in 0.3 s and takes 152 MB after load (513 MB peak). Compilation
now also switches off trips whose times run backwards (one İZBAN trip), which exposed an invalid
plan that the verifier rejected.

| Mode | Processes | Feasible | None | Incomplete | p50 | p95 | Queries per second |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Exact | 1 | 13 | 14 | 13 | 1.42 s | 3.17 s | 0.79 |
| Exact | 4 | 13 | 14 | 13 | 1.54 s | 3.47 s | 2.67 |
| Fast | 1 | 26 | 14 | 0 | 0.56 s | 1.49 s | 1.66 |
| Fast | 4 | 26 | 14 | 0 | 0.63 s | 1.65 s | 5.2 |

On the full network three alternatives cost much more, because walking links multiply the
candidate chains: 23 meetings, 3 incomplete, p50 1.77 s and p95 8.5 s on one process. The API
defaults to one alternative.

Fast mode finds meetings in 13 queries where the exact search ran out of its work budget, and no
emitted offer failed the verifier in either mode. The one-process p95 meets the 1.5 s target by a
small margin and four processes miss it slightly under contention. Raw rows are in
`experiments/results/v2/perf` and `perf-fast`.

## Consequences

Runs, clarification and verification still use the core schedule. A stateless `POST /v1/route` answers meeting queries on either network (`TRL_NETWORK`, default core) and reports an explicit `search_incomplete` when the work budget or the 20 s deadline ends the search. The full network is available through the library and
the benchmark script, and its plans are checked by `trl.verifier.sqlite_reference`, which reads
the raw archives instead of the compiled arrays. Fast mode removes most of the gap without a full range-RAPTOR. A profile-based search that
keeps alternatives is still not implemented.
