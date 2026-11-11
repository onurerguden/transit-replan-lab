# ADR 0001 · Pin the local model baseline

Date 2026-11-11 · Accepted

Use the Ollama tag `qwen3.5:4b-q4_K_M` as the first inference baseline. The local registry reported digest `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` for the downloaded artifact. The model advertises a 262,144-token context. The first probe used a 4,096-token context, temperature 0, seed 42, and thinking disabled to fit the local hardware and keep the output bounded.

On Apple M1 Pro with 16 GB and Ollama 0.40.16, a synthetic Turkish tram closure notice produced schema-valid JSON with `kind=stop_closure` and `target=Konak İskele`. Reproduce with `uv run --locked --project backend python scripts/probe_ollama.py` after starting Ollama and pulling the tag. The probe demonstrates schema support. Incident interpretation and negotiation quality will be measured separately.

Record the installed digest and configured context in every model run. Treat digest changes as new experimental conditions.

Sources [Model tag](https://ollama.com/library/qwen3.5:4b-q4_K_M) · [Structured output](https://docs.ollama.com/capabilities/structured-outputs) · [Ollama v0.40.16](https://github.com/ollama/ollama/releases/tag/v0.40.16).
