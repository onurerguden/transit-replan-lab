# Intake evaluation protocol

The development and calibration notices from v1.1.0 have been inspected.
Use them for paired diagnostics. Collect a fresh holdout before measuring
generalization beyond the existing phrase templates.

## Development comparison

Run rules, the same-vocabulary lexicon, Ollama base and the fused adapter
against the same bilingual case IDs. Use one clarification, the same
structured extraction schema and the same deterministic verifier. Each arm
starts with an empty route cache. Record model and prompt digests, latency,
original model replies, unsupported applications and nominal verifier errors.
Retain failed model attempts and score them as incorrect.

Report accuracy by language and event family. Bootstrap paired differences
over bilingual scenario groups. Compare fixed-order and impact-based questions
on feasibility and remaining meeting-time spread. Evaluate resilience over
the same seeded delay worlds and report successful arrivals and meeting time.
Compare coordination arms with identical offer pools and report worst rider
rank regret alongside agreement and latency.

## Independent holdout

1. Recruit two reviewers. Give notice authors the archived network and
   supported incident types. Keep production phrase patterns out of the brief.
2. Collect bilingual scenario groups with exact intended incidents or
   intentional ambiguity. Have the reviewers annotate independently and
   record disagreements, resolution and the reference clarification.
3. Freeze the labels, case inventory, source revision and primary metric
   before predictions. Keep gold labels and arm mappings private.
4. Shuffle anonymous arm IDs with a recorded seed. Have reviewers judge the
   proposed event and one-question outcome without seeing model identities.
   Join the ratings to the arm mapping after reviews close.
5. Report group-level intervals, disagreement and failure slices. Require
   zero unsupported applications and hard-constraint violations. Compare
   each model against the lexicon on accuracy and latency.

The holdout inventory uses the case schema in `experiments/vnext_cases.py`.
Store its JSONL and checksum manifest in a private directory. The exporter
produces `packet.jsonl` and `arm-key.json`. Share only the packet with reviewers.

```sh
uv run --locked --project backend python -m scripts.export_blind_review \
  .local/private-review/locked.jsonl .local/private-results/locked.jsonl \
  --output .local/blind-review-packet
```

Consider training when the base and lexicon share a reproducible error slice
on new development data and model behavior can change that outcome through
the production evidence gate. For the frozen synthetic diagnostic, all five
shared failures came from vocabulary and clock binding. Address that gate
on development data before training. Evaluate a later model on a fresh
independent holdout.

## TRL-Bench v3 annotation packet

`scripts/export_review_packet.py` samples 100 bilingual groups (200 reports) from the v3 test
split, shuffles them under anonymous ids and writes `packet.csv` and `INSTRUCTIONS.md` to
`.local/review-packet`. The key that maps ids to benchmark reports and gold labels is written to a
separate private directory and is never placed next to the packet. Give each of two annotators their
own copy and ask them not to discuss it.

```sh
uv run --locked --project backend python -m scripts.export_review_packet
uv run --locked --project backend python -m scripts.review_agreement a.csv b.csv
```

The second command prints Cohen's kappa for the action and the event, lists the disagreements for
adjudication, and counts how often each annotator matches the generated label. Report the kappa
before any adjudicated label is used, and keep reviewed reports out of later training. The packet was annotated
by five LLM annotators (two Claude model tiers at different effort levels) working from the packet alone. Pairwise
kappa for action and event ranged from 0.992 to 1.000. Their only disagreement was `r0150`, which carries an explicit
service-day date. Against the generated labels they matched 187 to 188 of 200 actions and 199 to 200 events. The
differences are 12 reports that name only "Konak", where the generated label is `ask` because the name is shared by two
stops. The annotators were not given the stop catalogue. Annotators from one model family are not independent of each
other, so read this as a consistency check and not as a measure of human agreement.
