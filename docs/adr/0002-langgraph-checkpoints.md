# ADR 0002 · Separate execution checkpoints from application state

Date 2026-11-11 · Accepted

LangGraph provides durable graph execution and resumable clarification. Use `AsyncSqliteSaver` from `langgraph.checkpoint.sqlite.aio` and synchronous durability for checkpoints. Version the execution thread by run and incident. Use `Send` to fan out independent rider views. Use `interrupt()` and `Command(resume=…)` for a typed clarification.

Only application tables own route proposals, votes, and public events. Graph nodes commit their business step under a deterministic key and current-version check before returning. A crash between that commit and its checkpoint may replay the node, so write effects must be idempotent.

The pinned dependency probe closes the SQLite saver after the interrupt, opens it again, resumes the thread, and verifies two separate `Send` branches return.

Sources [Checkpointers](https://reference.langchain.com/python/langgraph/checkpoints) · [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) · [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).
