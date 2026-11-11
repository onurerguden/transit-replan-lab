# ADR 0005 · Keep the rules default and ground incident targets

Date 2026-11-11 · Accepted before the locked run

In the 24 development scenarios at revision `2e550d1`, all four coordinators verified the 14 reference-feasible cases with exact incidents. Rules returned the expected outcome in 24/24 cases with p95 0.38 s. Five roles returned the expected outcome in 20/24 cases with p95 11.68 s. The five-role option missed the preregistered accuracy gain and latency threshold, so the default remains rules.

The three model variants guessed a target for each of four notices that named only Konak. The input did not distinguish the Metro station from the tram stop. Before the locked run, add a common catalogue resolver. Model output must agree with a uniquely supported stop or trip. The resolver does not change offers, votes, rider constraints, model weights, or the frozen cases. An unsupported or ambiguous target leads to clarification.

Development and locked rows record their distinct code revisions. Development measures the earlier intake behavior and informs the design decision. Locked measures the revised application with the same model and feeds. Compare architectures within each partition.
