# Bilingual operator notices

This synthetic dataset contains 360 training examples, 60 development examples, and 60 held-out examples. Each partition balances Turkish and English and six families: closures, cancellations, delays, ambiguous names, missing timing, and unknown stops. Examples reference a small catalogue sampled from the two pinned schedules. The catalogue includes stable IDs and distractors.

The generator assigns disjoint surface templates by split, checks that raw notice text does not overlap across splits, and hashes each JSONL file. Repeated stop and trip entities are in-domain. The task measures transfer across template families, with no independent claim about unseen networks, service operators, or real dispatch messages. All notices are synthetic.

Base and adapted Qwen3.5 use the same MLX build, model snapshot, chat template, greedy decoding, and 100-token completion cap. Exact match compares the parsed event and all relevant fields. A malformed response is scored as incorrect. The adapter is eligible only when development exact accuracy increases by at least five percentage points and correct clarification does not decrease. Select the outcome on development before reading the held-out scores. The route slice contains the first two premarked locked interchange cases and the first two premarked platform cases.
