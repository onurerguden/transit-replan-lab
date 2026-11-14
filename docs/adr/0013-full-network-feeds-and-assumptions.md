# ADR 0013 · Pin all five feeds, label calendar projections and generate footpaths

Date 2026-11-14 · Accepted · Updates [ADR 0004](0004-interchange-scope.md).

## Decision

- All five official archives are described in `feeds.json` with a mode, an optional flag, a calendar policy and the profiles that load them. `core` keeps Metro and the Konak tram line. `full` adds every tram line, İZBAN, ESHOT and İzdeniz.
- `trl feeds` reports each archive as `ok`, `projected_calendar`, `stale_calendar` or `unavailable`, with counts and quarantined trips. The report is committed and tested against the pinned bytes.
- An optional feed whose calendar does not cover the service day may repeat its weekly pattern. The report and the plan label this as an assumption. ESHOT (calendar ends 2026-10-09) and İZBAN (2023 data) use it. İzdeniz returns an HTML page and is skipped.
- Generated footpaths use 1.2 m/s, a 1.3 detour factor, a 60 s buffer and links up to 600 s. The buffer makes the table satisfy the triangle inequality without a closure pass. The two documented interchanges keep 480 s. Generated links have unknown accessibility.
- A gazetteer resolves stop names with Turkish case suffixes. A mention names a set of stops and never picks one.

## Consequences

The routing core still loads `core` as objects. The compiled timetable for `full` is built in a later phase from the same archives.
