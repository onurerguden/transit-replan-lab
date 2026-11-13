# ADR 0012 · Share one time grammar and verify model quotes instead of whitelisting them

Date 2026-11-14 · Accepted · Replaces the phrase equality check in [ADR 0006](0006-incident-evidence-and-walking-windows.md).

## Context

Two parsers read clock times, dates and durations with different rules. Both applied a report
for another day, read `+03:00` as 03:00, bound Turkish `10:00'a kadar` to the start, and ignored
`08.24`. Any negation anywhere in a report blocked the event, and a model's quote counted only
when it equalled one of eight fixed phrases, so a model could never beat the lexicon.

## Decision

- `trl.language.timeexpr` reads dates, zones, durations and clocks once. It binds roles from
  English prepositions and Turkish suffixes, carries a lone am or pm across a range when that
  reads sensibly and asks when both readings do, and writes overnight ranges in service-day
  seconds. A date other than the service day, a relative day or a zone other than Istanbul
  time makes the report unreadable, so the caller abstains.
- `trl.language.clauses` scopes negation, hedging and restoration to the clause that states the
  event. Parentheses, sentence ends, semicolons and contrast words end a clause.
- Both `intake` and the legacy `rule_notice` use these modules. Identifiers match in any case.
- A model's kind quote is accepted when it is at least four characters, appears verbatim and
  exactly once as whole words, sits in an unblocked clause and names a kind. The target and
  times still come from the deterministic parsers, so a quote never supplies evidence.
- `A and B closed` becomes one incident per stop when each part reads on its own.
- A trip can be named by a stop and a departure time (`the 08:15 departure from Konak`). It resolves only when exactly one trip running that day leaves the stop at that minute, and otherwise it names no trip.
- The request digest includes the prompt text. Recorded replay fixtures keep their earlier key.

## Consequences

`8:24 to 10:00 pm` now means 20:24–22:00 and `1,5 saat` means 5,400 s. Property tests cover
every clock from 00:00 to 47:59 in three formats, role binding in both languages, other days
and zones, and fabricated quotes. A nightly test runs 20,000 adversarial quotes.
