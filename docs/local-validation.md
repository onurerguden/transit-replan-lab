# Local model validation

The bundled demo was executed twice on Apple M1 Pro with 16 GB, Ollama 0.40.16, and the Qwen3.5 4B digest in [ADR 0001](adr/0001-local-model.md). Both executions ended with two current-version acceptances and a verified joint offer. The fixed-seed event signatures matched across these two executions. A third execution with the tight meeting window returned infeasible after one model call and a completed search.

| Case | Status | Calls | Prompt tokens | Output tokens |
| --- | --- | ---: | ---: | ---: |
| Konak closure, run 1 | Verified | 7 | 3,283 | 158 |
| Konak closure, run 2 | Verified | 7 | 3,283 | 158 |
| Tight meeting window | Infeasible | 1 | 845 | 47 |

Reproduce with `OLLAMA_BASE_URL=http://127.0.0.1:11434 uv run --locked --project backend pytest -m ollama backend/tests/test_agents.py -s`. These are smoke tests. The [experiment protocol](experiment-protocol.md) defines the comparative evaluation once that phase is reached.

## v1 release candidate

On 2026-11-12, a clean local clone passed locked dependency installation, lint, strict type checking, 25 backend tests, the frontend test, the production build, and four Playwright tests. The same clone built and started with Docker Compose. Its Nginx deployment passed the reconnection and route verification browser test. The production containers also reached local Ollama on the host and returned verified and infeasible outcomes for the two bundled scenarios. The verified real-model run used seven calls and 158 generated tokens.

The first [hosted Ubuntu CI run](https://github.com/onurerguden/transit-replan-lab/actions/runs/43115185956) passed the full workflow, including all four browser tests.
