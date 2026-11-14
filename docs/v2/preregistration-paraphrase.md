# TRL-Bench v3 · paraphrased test reports

Registered after the paraphrases were generated and before any arm read them.

## Data

The first 300 test groups were rewritten by `llama3.2:3b`, a model from a different family than the
reader. The rewriting model saw each report with its stops, times, trips, dates and delay
replaced by tokens, and had to return every token exactly once. A rewrite that dropped or repeated
a token, added a digit, answered in the wrong language or equalled the original was retried
twice and then dropped together with its pair. The values were restored afterwards. Gold labels
are those of the original reports. Prompts, raw replies, the model digest and the SHA-256 of the
result are in `data/bench/v3/PARAPHRASE.json`.

Limit: no second model judged whether a rewrite kept the meaning. A rewrite may soften or drop
a hedge or a negation. Such a case counts against the arm that reads it.

## Arms

Rules, the production phrase list, and the three adapter seeds from the model preregistration.
The gold-quote ceiling is not run because the original event phrase is usually absent from a
rewrite. The base model is not run because it produced no valid reply in the main run.

## Endpoints

Group-level exact correctness with cluster intervals, unsupported applications with their
Clopper–Pearson bound, and the change from the original reports for the same groups. Results are
reported whatever they are.
