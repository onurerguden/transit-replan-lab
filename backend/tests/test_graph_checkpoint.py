import asyncio
import operator
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import Command, Send, interrupt


class GraphState(TypedDict, total=False):
    notice: str
    roles: Annotated[list[str], operator.add]


class RiderState(TypedDict):
    role: Literal["rider_a", "rider_b"]


def clarify(state: GraphState) -> GraphState:
    reply: object = interrupt("Which stop is closed?")
    assert isinstance(reply, str)
    return {"notice": reply}


def collect_riders(_state: GraphState) -> list[Send]:
    return [Send("rider", RiderState(role=role)) for role in ("rider_a", "rider_b")]


def rider(state: RiderState) -> GraphState:
    return {"roles": [state["role"]]}


def test_sqlite_checkpoint_resumes_and_fans_out_after_reopen(tmp_path: Path) -> None:
    async def exercise() -> None:
        graph = StateGraph(GraphState)
        graph.add_node("clarify", clarify)  # pyright: ignore[reportUnknownMemberType]
        graph.add_node("rider", rider, input_schema=RiderState)  # pyright: ignore[reportUnknownMemberType]
        graph.add_edge(START, "clarify")
        graph.add_conditional_edges("clarify", collect_riders, ["rider"])
        graph.add_edge("rider", END)
        config: RunnableConfig = {"configurable": {"thread_id": "sample-run:1"}}
        database = str(tmp_path / "state.sqlite")

        async with AsyncSqliteSaver.from_conn_string(database) as saver:
            compiled = graph.compile(checkpointer=saver)  # pyright: ignore[reportUnknownMemberType]
            result = await compiled.ainvoke(  # pyright: ignore[reportUnknownMemberType]
                {"roles": []}, config, durability="sync"
            )
            assert result["__interrupt__"][0].value == "Which stop is closed?"

        async with AsyncSqliteSaver.from_conn_string(database) as saver:
            resumed = graph.compile(checkpointer=saver)  # pyright: ignore[reportUnknownMemberType]
            result = await resumed.ainvoke(  # pyright: ignore[reportUnknownMemberType]
                Command(resume="Konak İskele"),
                config,
                durability="sync",
            )
            assert result["notice"] == "Konak İskele"
            assert sorted(result["roles"]) == ["rider_a", "rider_b"]

    asyncio.run(exercise())
