# TRL-Bench v3 · language model arms

Registered before the adapter finished training and before any model read the calibration or
test splits. It extends the [main preregistration](preregistration.md).

## Arms

| Arm | Model |
| --- | --- |
| `base` | The local Qwen 3.5 4B weights used in v1, no adapter, prompt `operator_vnext.md` |
| `adapter` | The same weights with the LoRA adapter trained by `finetune/v2.yml` on 1,800 rows of the train split |

Both run in the MLX runtime with greedy decoding, 80 new tokens and thinking disabled. Replies
go through the same evidence gate as every other arm. A reply that is not a valid extraction
counts as no quote. A model cannot apply an incident on its own.

## Subsets

Running a 4B model over every report is slow on the available machine. The subsets are fixed
by rule before any reply exists.

- **Adoption set:** the first 100 dev groups at or above group 50 (200 reports).
- **Test subset:** the first 300 test groups (600 reports).

Rules and lexicon are compared on the same reports.

## Adoption rule

The adapter is adopted only if, on the adoption set, it answers correctly in more reports than
the base arm, the exact McNemar p value is below 0.05, and neither arm applies an unsupported
incident. Otherwise the adapter is not adopted and the result is reported as is.

## Reporting

The test subset is read once per model arm. The report lists correct counts with cluster
intervals, paired contrasts against rules, lexicon and the gold-quote ceiling, unsupported
applications with their Clopper–Pearson bound, parse failures, latency per report, and
accuracy by family and language.
