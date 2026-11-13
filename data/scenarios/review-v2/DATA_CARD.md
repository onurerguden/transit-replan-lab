# Synthetic holdout for the engineering follow-up

The implementation assistant authored the Turkish and English notices and
their intended incident fields. The freeze script checks the archived
timetable to derive feasible versus infeasible route labels. The independent
nominal route verifier checks feasible reference plans. The corpus covers
12 bilingual groups and 24 notices, including new wording outside the
supported lexicon, negation, service dates and timezone boundaries.

Commit the source and generated manifest before running predictions. The
primary metric is the exact event and expected terminal outcome. Count
unsupported applications and nominal verifier violations separately. Treat
bilingual groups as the unit for paired intervals. Report failures by family.

This is an authored synthetic holdout. No independent human authoring,
annotation or adjudication took place. Independent reviewers should use the
separate protocol and report their agreement and any label changes before
model identities are revealed.
