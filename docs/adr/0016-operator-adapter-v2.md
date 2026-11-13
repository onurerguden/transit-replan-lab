# ADR 0016 · Operator adapter v2: trained on the train split, not adopted

Date 2026-11-14 · Accepted

## Context

The v1.1 adapter was trained on phrases that the server also whitelisted, and its training loss
reached zero, so its gains could not be separated from memorization. The evidence gate now
accepts a model's event quote when the text supports it, which makes a model's contribution
measurable: it can supply the event kind for phrases outside the production list.

## Decision

- Train a LoRA adapter (rank 8, eight layers, 600 iterations, one seed, learning rate 1e-4) on 1,800 rows drawn only from the TRL-Bench v3 train split. A row asks for the quote and kind of the event phrase, or for nothing when the report names no event, denies it or hedges it. Validation uses the first 50 dev groups. The final training loss was 0.03 and the validation loss 0.05, not zero.
- Evaluate base and adapter in the MLX runtime with greedy decoding on a preregistered adoption set (200 dev reports) and a preregistered test subset (the first 600 test reports).
- Adopt the adapter only if it beats the base arm on the adoption set with an exact McNemar p below 0.05 and applies no unsupported incident.

## Result

On the adoption set every arm scored 200 of 200, because dev phrases are in the production
list, so the adapter cannot beat the base arm there. By the registered rule it is **not
adopted**.

On the test subset the adapter read 59.5% of 600 reports exactly (95% interval 52.4–67.1%). Rules,
the phrase list and the base arm read 53.7%. A gold quote of the event phrase would reach 96.2%.
The adapter improved 35 reports and worsened none against the base arm (exact p below 0.0001), all of them
ambiguous-stop reports. It learned to quote `late` and `cancelled` and to answer an empty
extraction for denials, but it returned no quote for the new closure predicates in
`closure_range`, `closure_from`, `closure_until`, `closure_note` or `closure_pair`. No arm applied an unsupported incident
(upper bound 0.61%). Replies took 0.93 s at the median (p95 1.11 s).

The base arm produced **no schema-valid reply in 600** because free decoding does not follow the
extraction schema. In production the Ollama structured-output constraint fixes the schema, so
that row measures format compliance in this runtime, not language ability.

## Consequences

The default operator stays deterministic. The adapter is kept as a measured negative result and
as the starting point for a corpus that includes the held-out predicate types in training under
a new split. One seed and a 4B model limit what this run shows.
