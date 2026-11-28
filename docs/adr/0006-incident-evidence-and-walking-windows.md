# ADR 0006 · Ground complete incidents and preserve terminal walking windows

Date 2026-11-12 · Status accepted for hardening

## Context

The model-backed Operator could use an identified stop with different clock values from the notice. The route search used the earliest possible departure for every walk. At a meeting stop, that discarded routes whose riders could wait before the final walk and arrive within their destination wait limit.

## Decision

The Operator's typed event must equal the event supported by explicit evidence in the notice. For a closure the gate checks action, one target, and both service times. For a trip it checks action, the scoped trip ID, its service on the simulated date, and any delay amount. Conflicts and missing evidence go through clarification. This is a deliberately limited TR/EN grammar with conservative abstention.

For a walk into a meeting stop, retain inclusive departure windows between closures. For each pair of route windows, intersect the possible meeting intervals. Choose the earliest common meeting, then the earliest arrival in each window that respects the rider's wait limit. Upstream waiting stays outside the walk. Other walking connections retain the earliest arrival for onward boarding. Both search and verification require the meeting stop to stay open from the first arrival through the meeting.

## Consequences

The search keeps one canonical timing per compatible pair of route windows. It returns a search-incomplete outcome if the label, window, or pair budget is exhausted. The verifier still reconstructs every exact leg and checks both votes independently. A completed search, a failed search, and an unverified proposal remain distinct in the browser.

The historical release experiments measure their recorded revisions. Re-evaluation uses the development split and a separate output directory.
