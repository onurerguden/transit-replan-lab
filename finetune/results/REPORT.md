# Operator LoRA results

Apple M1 Pro, 16 GB · MLX-LM 0.32.0 · Qwen3.5 4B 4-bit · seed 42

The 25-step pilot and 360-step training run completed. Full training took 915.65 s.
The GGUF adapter SHA-256 is `c460c37eea5deb18bf90ece593aa94174b136df2870be30288113752f6f88f5f`.

| Partition | Model | Exact match | Correct clarification | Schema-valid |
| --- | --- | ---: | ---: | ---: |
| Development | base | 0/60 | 0/30 | 0/60 |
| Development | adapter | 47/60 | 30/30 | 60/60 |
| Held-out | base | 1/60 | 0/30 | 1/60 |
| Held-out | adapter | 50/60 | 30/30 | 60/60 |

The development exact-match change was **+78.33 points** with **+30 correct clarifications**. The adapter was **not adopted**.

## Ollama route slice

| Case | Base outcome | Adapted outcome | Exact incident | Hard violation |
| --- | --- | --- | --- | --- |
| `locked-interchange-00` | verified | verified | True | False |
| `locked-interchange-01` | verified | clarification | False | False |
| `locked-platform-00` | infeasible | infeasible | True | False |
| `locked-platform-01` | infeasible | clarification | False | False |

## Error example

`test-closure-05` expected `{"kind": "stop_closure", "end": "16:54", "start": "16:12", "stop": "tram:5"}` and produced `{"kind": "clarify"}`.
