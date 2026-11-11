# Local model validation

The bundled demo was executed twice on Apple M1 Pro with 16 GB, Ollama 0.40.16, and the Qwen3.5 4B digest in [ADR 0001](adr/0001-local-model.md). Both executions ended with two current-version acceptances and a verified joint offer. The fixed-seed event signatures matched across these two executions. A third execution with the tight meeting window returned infeasible after one model call and a completed search.

| Case | Status | Calls | Prompt tokens | Output tokens |
| --- | --- | ---: | ---: | ---: |
| Konak closure, run 1 | Verified | 7 | 3,283 | 158 |
| Konak closure, run 2 | Verified | 7 | 3,283 | 158 |
| Tight meeting window | Infeasible | 1 | 845 | 47 |

Reproduce with `OLLAMA_BASE_URL=http://127.0.0.1:11434 uv run --locked --project backend pytest -m ollama backend/tests/test_agents.py -s`. These are smoke tests. The [experiment protocol](experiment-protocol.md) defines the comparative evaluation once that phase is reached.
