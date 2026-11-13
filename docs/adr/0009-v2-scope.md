# ADR 0009 · Extend the scope to the full İzmir network for v2

Date 2026-11-13 · Accepted

## Context

v1 covered Metro M1 and Konak Tram, four coordination variants, local inference and a
reproducible release. Live transit, additional networks and hosted demos were outside v1. The
engineering review behind the [v2 plan](../v2/engineering-plan.md) found that the small network
and the small, co-designed benchmarks limit what the measurements can support.

## Decision

- v2 loads all five official İzmir GTFS feeds through a feed-agnostic loader: Metro, every tram line, İZBAN, İzdeniz and ESHOT.
- The `core` profile keeps the v1 network and remains the demo default.
- A feed that is unavailable or has a calendar that does not cover the service date gets an explicit status and a labelled policy instead of failing the load.
- A model-free hosted demo is in scope. Deployment requires maintainer approval.
- Live transit data, rider accounts and travel advice remain out of scope.
- The release is 2.0.0 because commands, statuses and the stored schema change. A numbered migration upgrades v1.2.0 databases.

## Consequences

The routing engine must scale beyond the label search used in v1, and the benchmark must be
regenerated from the larger catalogue. Simulated incidents, generated footpaths and calendar
projections are labelled as assumptions in the data and the interface.
