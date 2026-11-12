# Bilingual disruption benchmark

The corpus has 80 development, 60 calibration, and 120 locked notices. Each
partition pairs Turkish and English descriptions of the same synthetic
incident. A semantic group stays within its partition. The six families cover
canonical notices, indirect reports, competing targets, clock and delay
formats, conflicting reports, and missing answers.

The generator records the expected intake action, allowed simulated answer,
exact text spans and reference outcome before inference. Manifest checks cover
bytes, bilingual groups, masked templates and active GTFS IDs. The archived
GTFS schedules are attributed in the [schedule data card](../../gtfs/SOURCES.md).
The notices and user replies are synthetic.

## Independent review

The reviewer sampled both languages without seeing model outputs. The reviewer
then read the raw GTFS CSVs and independently enumerated feasible timed rides
and transfers. The route labels matched all 60 locked groups, with 33 feasible,
seven infeasible, and 20 abstained. All 14 locked trip notices reference a
service in the relevant window. In development, one bilingual trip group
references a valid service outside its tighter meeting window.

Manifest SHA-256
`9a84b3e5f4f74f1007c131430a3ae14a84e984fcf4e8138330d8de70cd3dc648`.

Locked JSONL SHA-256
`cdd6d8c9354dcb1e5029dbe2734c6e78b2b741f08e03e0b6478fd446668e0415`.

The scripted replies support a controlled comparison of question policies.
The benchmark measures this archived network and these authored notices.
