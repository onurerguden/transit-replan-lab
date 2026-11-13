# Engineering review implementation

Work branch `review/evidence-and-correctness` builds on the published
[v1.1.0 source tree](https://github.com/onurerguden/transit-replan-lab/tree/v1.1.0).
The [initial review](review-2026-11-13.md) records the baseline findings.

| Area | Change and evidence |
| --- | --- |
| Incident grounding | vNext clarifications share date and time-zone validation with the original report. The HTTP test reopens the database before sending a UTC answer and asserts abstention, zero offers and zero votes. |
| State and recovery | The revision owner holds a local file lock. The terminal-state guard covers late steps, votes, reservations and model results. The fault test starts a contender while a model call is pending, kills the owner and verifies one finalization. See [ADR 0008](adr/0008-terminal-state-and-replay-integrity.md). |
| Model decisions | Durable replies require matching role-view fingerprints. The coordinator also checks the stored first choices and analyst choice against the current offer pool. |
| Candidate search | The optional margin-aware frontier preserves the better transfer in the same-arrival regression. The development comparison found a robust-policy regression in one group, so the application retains the original frontier. |
| Experiments | Per-directory locking, exclusive artifact creation, split manifests and an audit command protect results and detect incomplete or altered runs. JSONL retains raw model replies and schema or transport failures. |
| Operator | The lexicon is available in the UI and API. The API test exercises an indirect notice with zero model calls and two current votes. The existing release-default policy remains in effect. |
| Interface | The decision summary and clarification controls precede the maps. Route patterns and rider numbers carry meaning alongside color. Chromium exercises offer switching, reconnect, 390 px layout and a 320 px keyboard flow without WebGL. |

## Measurements

The paired development and calibration runs used Ollama 0.40.16 with matching
structured output, prompt, seed and context. The conditions files record the
exact source and model digests. The model tags were reconstructed locally
from the base text GGUF and fused adapter and have different manifests from
the original release.

| Arm | Development | Calibration | Inference calls across both splits |
| --- | ---: | ---: | ---: |
| Rules | 66/80 | 50/60 | 0 |
| Lexicon | 80/80 | 60/60 | 0 |
| Base hybrid | 80/80 | 55/60 | 24 |
| Fused adapter | 80/80 | 60/60 | 24 |

Across 560 observations there were zero unsupported applications and zero
nominal route verifier violations. All five adapter gains over the base
were English calibration paraphrases. The lexicon resolved those examples
as well. These are diagnostics on previously inspected notices. The
[development report](../experiments/results/review-2026-11-13/dev.md) and
[calibration report](../experiments/results/review-2026-11-13/calibration.md)
include language slices, timing, and grouped intervals.

```sh
uv run --locked --project backend python -m experiments.vnext_cases
# BASE_TAG and ADAPTER_TAG refer to the local text and fused GGUF imports.
TRL_OLLAMA_MODEL="$BASE_TAG" uv run --locked --project backend \
  python -m experiments.vnext_runner --split dev \
  --arms rules lexicon hybrid adapter --adapter "$ADAPTER_TAG" \
  --output .local/reproduction
uv run --locked --project backend python -m scripts.audit_experiment_bundle \
  .local/reproduction --split dev
```

Use `--split calibration` for the paired calibration run. The
[development conditions](../experiments/results/review-2026-11-13/dev-conditions.json)
record the evaluated tags, source digest and runtime. The base and fused
Ollama tags require local weights. The [training record](../experiments/results/vnext/training.json)
identifies the fused artifact by SHA-256.

The [mediation diagnostic](../experiments/results/review-2026-11-13/mediation.md)
uses seven identical offer pools across arms. Rules and five roles with
counteroffers reached 7/7 agreements, one model reached 6/7 and five roles
without counteroffers reached 0/7. The added transfer/arrival conflict accounts
for the difference between rules and one model. The walking preference still
needs a fixture where it changes the available trade-off. The same successful
arms averaged one rank of worst-rider regret. This sample supports retaining
rules as the default coordinator.

The training audit matched four published artifact hashes and found 20 exact
overlaps in the original validation data. The
[revised corpus audit](../experiments/results/review-2026-11-13/training-data-audit.json)
found zero exact or grounded event overlaps and six balanced family/language
strata. The same template families appear across splits. The revised corpus
has not been used to train an adapter.

Across 23 feasible development groups and 2,944 shared delay worlds, the
original frontier produced 2,676 early and 2,913 resilient successes. The
margin-aware frontier produced 2,694 early and 2,900 resilient successes.
The difference in resilient successes came from one group. See the paired
[default frontier](../experiments/results/review-2026-11-13/resilience-default.jsonl)
and [margin-aware frontier](../experiments/results/review-2026-11-13/resilience-margin.jsonl) rows.

The 30-run in-process API samples measured p95 518.37 ms on the baseline and
445.23 ms on the updated branch, both with zero model calls. The samples were
collected in separate runs with concurrent local development checks. Treat
the difference as a regression check on this machine, with load and run order
as possible confounders.

## Verification and recovery

- Fresh dependency installation and production build passed. The local CI
  commands passed with 73 deterministic backend tests, the frontend unit
  test, and about 97% coverage across the four configured backend modules.
- Eleven browser scenarios passed against the host stack. Twelve passed against
  the production Docker stack, including the lexicon operator flow. The Docker
  suite is also wired into the GitHub workflow.
- Two tests passed with real Ollama. The Docker API separately produced a
  verified result with two votes, an infeasible result with zero votes, and
  an ambiguity response with zero model calls. The unavailable model check
  produced a model error without an applied incident or votes.
- The SQLite backup API captured a baseline database. The updated application
  opened it, and the original application opened the restored backup. Both
  recovered the same verified offer and two votes.
- Before rollback, stop the API, retain the current volume, and restore the
  consistent pre-upgrade backup into a separate volume. Start the previous
  image with that volume and verify a known completed run before switching.

The [independent evaluation protocol](review-evaluation-protocol.md) and
packet exporter are ready. A new set written and rated by independent reviewers
is the remaining research dependency. The hosted GitHub run and release tag
depend on publication of the branch.
