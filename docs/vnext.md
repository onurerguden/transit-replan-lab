# Evidence-led replanning

The bundled ambiguous closure names Konak İskele and Karataş. Their timetable
previews differ in feasibility. Selecting Konak İskele enables two joint offers:
an earlier arrival and a later arrival with a larger transfer margin. The
evidence panel shows the source report, synthetic scenario counts, and the
independent nominal timetable check. The two-minute counterfactual replays the
fixed journey with a delay on its tightest incoming connection.

## Local verification

Start the no-key replay application.

```sh
docker compose up --build --wait
```

Open the ambiguous closure scenario, expand **Run settings**, and select
**Most resilient**. Apply the report, choose **Konak İskele (Tram)**, and inspect
the joint offers. An archived v1 screen is available at `/?workflow=legacy`.
Choose the Ollama runtime to exercise hybrid extraction with the local Qwen
checkpoint. The release-default operator checks the installed model digest.

```sh
make setup
make check
make build
TRL_MODEL=replay make e2e
TRL_MODEL=ollama make test
```

Local metrics separate intake, route selection, and model calls. The probability
display is a count across a versioned synthetic delay profile. It reflects this
simulation and the archived timetable.

## Reproduce the experiment

Generate and validate the bilingual corpus before inspecting predictions. The
generator emits data and hashes in `.local/vnext-benchmark`.

```sh
uv run --locked --project backend python -m experiments.vnext_cases
uv run --locked --project backend python -m experiments.vnext_runner --split dev
uv run --locked --project backend python -m experiments.vnext_runner --split calibration
uv run --locked --project backend python -m experiments.vnext_mediation
```

The scenario evaluator has paired TR/EN cases. The report resamples semantic
groups, and the simulated clarification answers follow the same rules for all
question policies. Run the locked partition with the frozen conditions only.

For the Operator adaptation, run `python -m finetune.vnext_data` using the
project runtime. Use the existing MLX pilot and training configuration with
`data: .local/vnext-training` and separate output directories. Export and fuse
the adapter using the pinned toolchain in the training guide, then compare
it under the same Ollama structured output with
`--arms hybrid adapter --adapter trl-vnext-operator:qlora`.
[Training and export guide](../finetune/README.md).

[Architecture decision](adr/0007-compare-disruption-hypotheses.md).

## Results and release decision

The 120 locked notices form 60 bilingual groups. Hybrid and QLoRA both achieved
120/120 correct outcomes and 20/20 automatic paraphrase decisions. The vNext
rules arm achieved 100/120. Across all 720 comparisons the offline evaluator
observed zero unsupported applications and zero hard-constraint violations.
Fixed-order and impact-based questions tied on the locked corpus. The general
question requested 180 fields and the targeted policies requested 60 under the
same simulated answer rules. A separate controlled test checks that impact-based
selection prefers the field that changes feasibility when two slots compete.

The original Qwen is the release default when Ollama reports the pinned model
digest. QLoRA matched the base on development and locked outcomes and improved
calibration from 55/60 to 60/60. It missed the preregistered development gain
threshold. The adapter was exported and tested with the same constrained
Ollama output schema. The base remains selected.

In six fixed preference conflicts, rules, one model and five roles with a
counteroffer all reached 6/6 verified agreements. The five-role arm reached
0/6 with the counteroffer disabled. The rules arm reached p95 0.46 s. The
five-role arm reached p95 16.09 s. Keep rules as the default coordinator.

[Locked results and raw rows](../experiments/results/vnext/locked.md) ·
[Preregistered gates](../experiments/results/vnext/freeze.json) ·
[Calibration](../experiments/results/vnext/calibration.md) ·
[Mediation](../experiments/results/vnext/mediation.md) ·
[Independent data review](../data/scenarios/vnext/DATA_CARD.md)

## Route and system profile

Across 33 independently checked feasible incident groups and 4,224 synthetic
worlds, the earliest offers succeeded in 3,891 worlds and the resilient offers
in 4,166. The resilient choice improved 18 groups. Their median later meeting
was 450 seconds. In the bundled demo the scores are 109/128 and 128/128.

The canonical HTTP command reached verified state in p50 323.50 ms and
p95 373.19 ms across 15 runs on the M1 Pro, with zero model calls. On the
same demo candidates, sharing equivalent delay assignments reduced the
comparison-stage p95 from 25.48 ms to 5.69 ms. Both stage measurements ran
in the same process and share its peak RSS measurement.

[Route results](../experiments/results/vnext/resilience.jsonl) ·
[Command profile](../experiments/results/vnext/api-profile.json) ·
[Comparison profile](../experiments/results/vnext/performance.json) ·
[Training provenance](../experiments/results/vnext/training.json)

```sh
uv run --locked --project backend python -m scripts.profile_vnext --output .local/api-profile.json
uv run --locked --project backend python -m scripts.evaluate_resilience --output .local/resilience.jsonl
```

## Release verification

58 deterministic backend tests, two real Ollama tests, the frontend unit
test, and 10 Chromium scenarios passed. The browser suite ran against the
Docker package. An isolated rollback exercise verified the same legacy run
and two votes on the previous image, on vNext, and on the restored
pre-upgrade SQLite backup with the previous image.
