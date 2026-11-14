# Operator adapter v3 and retrieval comparison

TRL-Bench v3.1, preregistered in `docs/v2/preregistration-operator-v3.md` and amended before any
test report was read. Every model arm runs through Ollama structured output at temperature 0.
Raw replies are in `replies/`, per-report scores in `bench-test/` and `bench-dev/`.

## Test: hard slice, even-numbered groups (616 reports, 308 groups)

| Arm | Correct | 95% cluster interval | Unsupported (upper bound) |
| --- | ---: | --- | ---: |
| Production lexicon | 50 (8.1%) | [5.7%, 10.9%] | 0 (0.60%) |
| Base model `qwen3.5:4b-q4_K_M` | 112 (18.2%) | [14.9%, 21.8%] | 2 (1.17%) |
| Base model with 4 retrieved train examples | 516 (83.8%) | [80.7%, 86.6%] | 0 (0.60%) |
| **Adapter, seed 42** | **552 (89.6%)** | **[87.2%, 92.0%]** | **0 (0.60%)** |
| Gold quote (ceiling, not a model) | 616 (100%) | | 0 (0.60%) |

Preregistered contrasts, paired over the same reports (cluster bootstrap, 10,000 draws; exact
McNemar with Holm adjustment):

| Contrast | Difference | 95% cluster interval | Only left right | Only right right | Holm p |
| --- | ---: | --- | ---: | ---: | ---: |
| adapter − lexicon | +81.5 pts | [+78.3, +84.5] | 502 | 0 | < 0.0001 |
| adapter − base | +71.4 pts | [+67.6, +75.0] | 443 | 3 | < 0.0001 |
| adapter − base with retrieval | +5.8 pts | [+2.6, +9.1] | 70 | 34 | 0.0005 |
| base with retrieval − base | +65.6 pts | [+61.5, +69.6] | 414 | 10 | < 0.0001 |

By family (correct / reports):

| Family | Lexicon | Base | Retrieval | Adapter | Gold quote |
| --- | ---: | ---: | ---: | ---: | ---: |
| ambiguous_stop | 0/76 | 16/76 | 55/76 | 62/76 | 76/76 |
| closure_from | 0/78 | 6/78 | 65/78 | 70/78 | 78/78 |
| closure_note | 0/76 | 3/76 | 64/76 | 73/76 | 76/76 |
| closure_pair | 0/78 | 11/78 | 63/78 | 72/78 | 78/78 |
| closure_range | 0/78 | 8/78 | 61/78 | 71/78 | 78/78 |
| closure_until | 0/76 | 2/76 | 69/76 | 62/76 | 76/76 |
| hedged | 38/76 | 50/76 | 75/76 | 73/76 | 76/76 |
| negated | 12/78 | 16/78 | 64/78 | 69/78 | 78/78 |

The lexicon scores almost nothing on closures because the test wording was written by a model of
another family and avoids the production word list by construction. The gold-quote arm reads every
test report, so each error of a model arm is an error of its quote.

## Seeds on the test subset

| Seed | Correct | 95% cluster interval | Unsupported |
| --- | ---: | --- | ---: |
| 42 (registered `adapter` arm) | 552 (89.6%) | [87.2%, 92.0%] | 0 |
| 43 | 568 (92.2%) | [89.9%, 94.3%] | 0 |
| 44 | 548 (89.0%) | [86.4%, 91.4%] | 0 |

The range is 3.2 points, inside the registered 5. Seed 42 is also the median seed on test. Seeds 43
and 44 were first left out to save time and run afterwards on the same reports.

## Adoption rule

| Condition | Result |
| --- | --- |
| Adapter − lexicon lower bound above 0 | +78.3 pts, met |
| Adapter − base with retrieval lower bound above 0 | +2.6 pts, met |
| No unsupported application | 0 of 616, met |
| Seed range at most 5 points | 3.2 points, met |

The adapter is adopted as the recommended local Operator.

## Development: hard slice, first 400 reports

| Arm | Correct | 95% cluster interval |
| --- | ---: | --- |
| Production lexicon | 55.0% | [49.8%, 60.0%] |
| Base model | 57.8% | [52.5%, 62.6%] |
| Base model with 4 retrieved examples | 97.0% | [95.2%, 98.5%] |
| Adapter, seeds 42 / 43 / 44 | 100% / 100% / 99.5% | |

Dev wording is close to the training wording, so dev overstates the adapter. The test wording is
new. Retrieval depth was not compared; k = 4 was used (preregistration amendment 1).

## The first dev run found a schema defect

The first dev run scored the adapters at 60.8–62.5% and the base model at 53.5%. No reply of any arm
stated `kind`, although every training row did. Ollama's constrained decoding skips an optional
field, and the evidence gate reads the event kind from that field, so model quotes were ignored.
Requiring `kind` in the schema sent to Ollama (`trl.vnext.ollama_format`) moved the adapters to
99.5–100% on the same reports. The first run is in `dev-first-run/`.

## Other measurements

- Latency per request with four requests in flight: adapter median 4.5 s (p95 6.1 s), base 8.4 s
  (p95 12.9 s), base with retrieval 9.4 s (p95 24.7 s). These are throughput-run latencies, not
  single-request times. In smoke runs a single base-model request took about 2 s.
- The base model stated a `kind` in 88 of 616 replies. The adapter did in all 616. Retrieval did in 586.
- Two base-model replies applied an unsupported incident. The adapter and retrieval arms applied none.
- The fused Ollama adapter does not reproduce the MLX adapter's replies one for one. Seed 42 of adapter
  v2 matched its MLX replies on 25 of 200 dev quotes, and every arm scored 200 of 200 there. The Ollama
  models are what is evaluated.

## Limits

- One model, one runtime, one machine. The 616 test reports are the even-numbered half of the hard slice.
- The test predicates, lead-ins, notes, calm lines, negations and hedges were written by Llama 3.2 3B.
  Its Turkish is the weakest part: seven sealed Turkish parts that the reader could not bind even
  with a gold quote were dropped, and the remaining Turkish phrases were not checked by a person.
- The train banks were written for the same generator, so a distribution shift beyond these
  constructions is untested. Real notices were not used.
- Retrieval depth, a second adapter configuration and an adapter trained with retrieval were not run.
