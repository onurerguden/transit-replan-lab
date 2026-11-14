# Transit Replan Lab v2: evidence-gated replanning on the İzmir network

## Problem

After a disruption two riders need a place and time to meet. A report arrives as free text in
Turkish or English. A system that acts on it must avoid the worst failure: confidently applying
an event the text does not support, then verifying a plan built on it. Version 1 showed that the
pipeline worked on a small network and a small phrase set, but several of its strongest results
held by construction, and the reader could apply a report for another day or read `+03:00` as a
clock time. Version 2 fixes those defects, widens the network and measures the reader on data
the system was not built against.

## System

A run is a sequence of revisions. A command (report, answer, retraction, retry) opens a revision.
A worker holding an execution lease reads the report, searches for joint offers and asks two
rider roles to accept one. A plan is **verified** only when two riders accept the same offer in
the current revision and a verifier that shares no code with the router passes every leg.

**State.** Statuses and the transitions between them live in one table. SQLite holds runs,
events and leases. Every guarded write checks its fencing token in the writing transaction, so a
worker started before a command cannot write after it. Execution checkpoints are separate and
pruned. Numbered migrations back the database up and upgrade a database written by v1.2.0
without changing any view, event or idempotent receipt.

**Closures.** A rider may not be present at a closed stop at any second. The router prunes
departures that wait through a closure. The verifier derives presence intervals from the plan
and tests them against its own incident semantics. A Hypothesis oracle enumerates journeys on
random networks with mid-trip boarding, pickup and drop-off flags, closures, a cancellation, a
delay and wait limits. The router's optimum equals the oracle's, every emitted offer verifies,
and a one-second mutation of a leg is rejected.

**Reading reports.** One grammar reads clock times (`08:24`, `08.24`, `saat 10'a kadar`),
am and pm, durations (`1,5 saat`), overnight ranges and zones. It binds Turkish suffixes and
English prepositions to start and end, refuses any other day or zone, and scopes negation,
hedging and restoration to the clause that states the event. A model may quote the phrase that
names the event and state its kind. The gate accepts the quote only when it appears verbatim,
once, as whole words, in an unblocked clause. The target and the times are always read by the
deterministic parsers, so a model cannot add evidence.

**Network.** Five official feeds are pinned and checked. A health report records each feed's
counts, calendar coverage and quarantined trips. ESHOT and İZBAN calendars do not cover the
demo day, so their weekly pattern is repeated and labelled as an assumption. İzdeniz serves a web
page instead of an archive and is skipped. The network compiles to arrays and a query is bounded by
a forward and a backward pass before the exact search.

## Evaluation

TRL-Bench v3 is generated from parts that belong to exactly one split. Its four splits hold 3,000,
600, 300 and 1,000 bilingual groups. Stops are partitioned, and a fifth only appear in test.
An audit proves that no phrase part, stop, exact text or masked template is shared, and that no
test predicate matches the production phrase list. A freeze manifest hashes the splits and the
generator. A preregistration was committed before calibration and test were read, and the
runner refuses to read the test split without it. Statistics are a two-level cluster bootstrap
over constructions and groups, exact McNemar tests with Holm adjustment, and Clopper–Pearson
bounds.

Building the benchmark found four defects in the reader (a hyphen between clocks read as a zone
offset, Turkish negation with a suffix, a report with no event that triggered a question, and a
colon treated as part of a clause). They were fixed on dev before the preregistration.

**Results.** On test, rules and the production phrase list read 51.4% of 2,000 reports exactly,
because the test phrases are outside the list. Adding a gold quote of the event phrase, which
bounds what any model can contribute through the gate, reaches 84.1%. No arm applied an
unsupported incident in 2,000 reports (95% upper bound 0.18%), including an arm that quotes
random words with random kinds. Reading the test failures showed two further defects, a Turkish
`Not:` label read as English negation and conjoined stops that ignored quotes. They were fixed
after the single preregistered run, and a labelled post-hoc re-run with the fixed reader gives
96.2% for the gold-quote arm. The preregistered numbers are the ones reported above.

**Language model arms.** A preregistered subset of 600 test reports was read once by the local
4B model without and with an adapter trained on 1,800 rows of the train split. Without the adapter
and with unconstrained decoding the model produced no schema-valid reply in 600, so it equals
the deterministic rules at 53.7%. The adapter produced 600 valid replies and read 59.5%
[52.4%, 67.1%] with the registered seed, and 77.7% and 76.8% with two further seeds trained afterwards. Against the base arm it gained 35 reports and lost none (exact p below 0.0001),
all in ambiguous-stop reports. With seed 42 it returned no quote for new closure wordings. Seeds 43 and 44 quote them in about half of the reports of each closure family. All three stay below the 96.2% ceiling. No arm applied an unsupported incident (upper bound 0.61%).
The adoption rule required a gain on the dev adoption set, where every arm is perfect because
dev phrases are in the production list, so the adapter is not adopted.

## Performance

On the whole network, with riders near a shared destination, one process answers at p50 1.56 s
and p95 3.6 s, four processes at 2.3 queries per second, using 513 MB at peak. Of 40 queries, 13
were incomplete under a two-million work-unit budget. The budget is deterministic and the
outcome is explicit. The exact search keeps one label per arrival second, which is expensive on
dense bus networks. Dominance across arrival times would remove most of that cost and is not
implemented.

## Threats to validity

- The benchmark and the system share an author, and no independent person wrote or labelled a report. Held-out constructions reduce this but do not remove it.
- The catalogue is 39 stops of the core network and reports use raw trip identifiers. Natural-language trip references are not supported.
- The gold-quote arm is an upper bound, not a language model. A real model's quotes may fail the gate.
- Plan outcomes were not labelled by two independent routers. The evaluation measures reading and clarification, and plans are checked by the verifier.
- ESHOT and İZBAN timetables for the demo day are projections.
- Results come from one machine and one model runtime. Adapter results vary by about 18 points across three seeds.
