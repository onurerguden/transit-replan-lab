# Preregistration · Operator adapter v3 and retrieval arm

Registered before any calibration or test report of TRL-Bench v3.1 is read by a model. Development
reports of v3.1 are used to choose configurations and have already been read.

## Question

Does a LoRA adapter trained on the v3.1 train split read events better than the production
lexicon, the unadapted base model, and the base model given retrieved train examples? The model's
only contribution is the quote that names the event (ADR 0012), so the comparison is about that
quote through the evidence gate.

## Data

- TRL-Bench v3.1, frozen in `data/bench/v31/FREEZE.json`. Test wording of another model family is
  in `data/bench/v31/sealed/test-parts.json`. Maintainers did not read it while building the system.
- The gold-quote arm reads every test family with 100% accuracy (`experiments.bench_v31.ceiling`),
  so every error of a model arm comes from the quote.
- The v3 test split was used once for adapter v2 and is not used again.

## Arms

| Arm | What reads the report |
| --- | --- |
| `lexicon` | The production reader with no model |
| `base` | `qwen3.5:4b-q4_K_M` in Ollama with structured output, prompt `operator_vnext` |
| `base_rag` | The same model, prompt `finetune/prompts/operator_rag.md` and the k nearest train examples |
| `adapter` | The adapter configuration chosen on dev, fused into the same Ollama base, prompt `operator_vnext` |

Every arm uses temperature 0, seed 42 and the same evidence gate and clarification policy. All
model arms run through Ollama so that the production path is what is measured. Model arms read the
hard slice only. In the other five families the lexicon already finds the event kind or the report
is refused before the model is asked, so the model is not consulted; the lexicon arm covers them.

## Choosing configurations (development reports only)

- The retrieval depth k is chosen from {2, 4, 8} on the accuracy of `base_rag` over the dev hard
  slice. Ties go to the smaller k.
- The adapter has one configuration, `finetune/v31-c1.yml` (rank 8, scale 16, eight layers, 600
  iterations), the recipe of adapter v2 trained on v3.1 data. A second candidate with rank 16 was
  dropped for compute time before any evaluation. Three seeds (42, 43, 44) are trained and fused
  into Ollama. The seed with the median dev hard-slice accuracy is the `adapter` arm. The other
  seeds are reported with it.

## Hard slice

The families whose outcome depends on the model's quote: `closure_range`, `closure_until`,
`closure_from`, `closure_note`, `closure_pair`, `ambiguous_stop`, `negated` and `hedged`. The test
hard slice has 1,232 reports in 616 groups.

## Primary endpoint

Accuracy over the test hard slice, where a report is correct when the action and the final incident
set match the generated label. Confidence intervals use the two-level cluster bootstrap of
`experiments.bench_v3.stats` (cluster by part combination, then by group), 10,000 resamples.

An adapter trained on retrieval-formatted rows was cut for compute time. The report says so.

## Contrasts (one Holm family, α = 0.05)

1. `adapter` − `lexicon`
2. `adapter` − `base`
3. `adapter` − `base_rag`
4. `base_rag` − `base`

Each contrast reports the paired difference with its cluster interval and the exact McNemar test.

## Safety endpoint

No arm may apply an unsupported incident. Report the count and the Clopper–Pearson 95% upper bound
over the test hard slice. Any unsupported application by a model arm blocks adoption of that arm.

## Adoption rule

The adapter replaces the unadapted Operator only if all of these hold on the test split.

1. The lower bound of the interval for `adapter` − `lexicon` on the hard slice is above 0.
2. The lower bound for `adapter` − `base_rag` is above 0. If not, retrieval is the candidate and is
   adopted only if its lower bound against `lexicon` is above 0.
3. No unsupported application.
4. The range of hard-slice accuracy across the three seeds is at most 5 percentage points.

Otherwise the result is reported as not adopted and the Operator default is unchanged.

## Also reported, not tested

Accuracy by family and language, schema-invalid and empty replies, latency per report, and the
agreement between each fused Ollama model and its MLX adapter on dev.

## Stopping rules

The test split is read once per arm. Results files open with mode `x`. If a run fails for a
technical reason, rerun the same arm with the same configuration and record the failure.

## Amendments (committed before any test report is read by a model)

1. **Retrieval depth.** To save compute time, k = 4 is used without the dev comparison of k = 2
   and k = 8. The three depths had not been compared when this was decided.
2. **Test subset.** Model arms read the even-numbered groups of the test hard slice (616 reports in
   308 groups), fixed before any test inference. The lexicon arm is scored on the same reports.
   Contrasts, intervals and the adoption rule apply to this subset.
3. **Schema.** The first dev run showed that no model reply stated `kind`, because Ollama's
   constrained decoding skips an optional field. `ollama_format` now requires it, in the
   production path and in the evaluator. The dev results above use the required field. The first
   dev run, without it, is kept under `.local` and reported as a finding.
4. **Adapter seed.** Dev hard-slice accuracy ties between seeds 42 and 43. The smaller seed, 42, is
   the `adapter` arm. Seeds 43 and 44 run on the same subset for the spread condition.
