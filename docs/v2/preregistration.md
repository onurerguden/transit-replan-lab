# TRL-Bench v3 preregistration

Committed before the calibration and test splits were read by any arm. The dev split was used
to find and fix four reader defects (hyphen ranges, Turkish negation with a suffix, reports
without an event, and a time-zone false positive). Those fixes are in the commit that precedes
this file.

## Data

`data/bench/v3` holds 3,000 train, 600 dev, 300 calibration and 1,000 test groups, each a
Turkish and English pair. `FREEZE.json` records the SHA-256 of every split and of the
generator. The audit proves that no phrase part, stop, exact text or masked template is shared
across splits and that no test predicate matches the production lexicon.

Limits: the generator and the system share an author, the stop catalogue is the 39
unambiguous stops of the core network (8 held out for test), reports use raw trip identifiers,
and no report was written or labelled by an independent person. The blind review packet
exporter remains available for future reviewers.

## Arms

| Arm | What it reads |
| --- | --- |
| rules | Deterministic grammar only |
| lexicon | Grammar plus the production phrase list as quoted evidence |
| model_ceiling | Grammar plus a quote of the gold event phrase with the gold kind. This bounds what any model can add through the evidence gate. It is not a language model. |
| model_adversarial | Grammar plus a random word quoted with a random kind. It tests the gate. |

No Ollama arm is registered. Any later model arm needs its own registration.

## Endpoints

- **Primary:** group-level exact correctness (the right action and the right final incident set) on the test split, rules and lexicon versus model_ceiling. The contrast is supported when the lower 95% bound of the paired cluster-bootstrap difference is above zero.
- **Safety:** unsupported applications, meaning an incident applied that the gold does not contain. The release requires zero on the test split for every arm, with the Clopper–Pearson upper bound reported.
- **Secondary:** accuracy by family, exact McNemar contrasts with Holm adjustment, and the ask-slot accuracy.

## Procedure

Calibration runs once to check that nothing is degenerate. Test runs once. Results are written
exclusively to `experiments/results/v2/bench` and reports are generated from those rows.
