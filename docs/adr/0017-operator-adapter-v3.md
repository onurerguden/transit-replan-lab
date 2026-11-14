# ADR 0017 · Operator adapter v3: adopted as the local Operator, with retrieval as the runner-up

Date 2026-11-14 · Accepted

## Context

Adapter v2 beat the rules on the v3 test split but was not adopted. Its adoption rule could not be
met, its seeds differed by 18 points, and the base model had no fair arm: it was run unconstrained in
MLX and never through Ollama's structured output. The v3 train bank also had only about 280 distinct
masked templates, so a model could not learn many ways to name an event.

## Decision

- Build TRL-Bench v3.1 (`experiments/bench_v31`). Phrase parts, sentence frames and the connectives of
  one-sided closures belong to one split. Train has 3,859 distinct masked templates. The test
  predicates, lead-ins, notes, negations and hedges come from Llama 3.2 3B, and the maintainers did not
  read them. Parts that the reader cannot bind even with a gold quote are removed by `ceiling.prune`.
  The v3 files and freeze stay untouched.
- Train a LoRA adapter on v3.1 (rank 8, eight layers, 600 iterations, three seeds) on 3,039
  deduplicated rows, fuse it into the Ollama base and evaluate every arm through Ollama structured
  output.
- Add a retrieval arm: the four nearest train reports, found by TF-IDF over masked character four-grams,
  are shown as examples. Retrieval never returns a report with the query's own template.
- Compare lexicon, base, base with retrieval and the adapter on the hard slice, as preregistered in
  `docs/v2/preregistration-operator-v3.md`.
- Require `kind` in the schema sent to Ollama (`trl.vnext.ollama_format`).

## Result

On 616 test reports of the hard slice the adapter reads 89.6% [87.2, 92.0], base with retrieval 83.8%
[80.7, 86.6], the base model 18.2% and the lexicon 8.1%. The adapter beats retrieval by 5.8 points
[+2.6, +9.1] (Holm p 0.0005) and the lexicon by 81.5 points. It applies no unsupported incident
(upper bound 0.60%); the base model applied two. Three seeds read 89.6%, 92.2% and 89.0% (range 3.2 points, inside the registered 5) and none
applied an unsupported incident.

The first dev run showed the schema defect: constrained decoding skipped the optional `kind`, so no
reply carried the event kind and the gate ignored every model quote. Requiring it raised the adapters
from about 61% to 99.5–100% on dev. Retrieval lifted the base model from 18% to 84% on test, so most of
the gain comes from showing the model the shape of a valid answer.

## Consequences

- All four registered conditions hold, so the adapter is adopted as the recommended local Operator. The
  default run stays model-free. To use the adapter, fuse `finetune/results/v31/adapter-s42` into the
  Ollama base as described in `finetune/README.md`, set `TRL_OPERATOR_MODEL` and ask for the hybrid
  mode. Retrieval is the runner-up and needs no training, but it costs a longer prompt.
- The reader now recognises a numeric date followed by a label colon (`17.11.2026:`). Before, such a
  notice could be applied to the service day.
- The preregistered adoption rule depends on the registered subset and seeds; see the amendments.
- Retrieval depth, a second adapter configuration and a retrieval-trained adapter were not tried.
- The results come from synthetic reports with wording written by one model family. They do not show
  how the adapter reads real notices.
