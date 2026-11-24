from typing import Any, Optional
import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from app.agent.nodes import (
    approval_handler_node,
    code_executor_node,
    code_generator_node,
    code_repair_node,
    error_analyzer_node,
    final_reporter_node,
    planner_node,
    requirement_analyzer_node,
)
from app.agent.state import AgentState
from app.core.config import get_settings


def route_after_approval(state: AgentState) -> str:
    if state.get("approval_status") == "rejected":
        return "final_reporter"
    return "code_generator"


def route_after_error_analysis(state: AgentState) -> str:
    test_results = state.get("test_results", {})
    is_success = bool(test_results.get("success", False))
    if is_success:
        return "final_reporter"

    repair_attempts = state.get("repair_attempts", 0)
    if repair_attempts < 3:
        return "code_repair"
    return "final_reporter"


def build_agent_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("requirement_analyzer", requirement_analyzer_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("approval_handler", approval_handler_node)
    workflow.add_node("code_generator", code_generator_node)
    workflow.add_node("code_executor", code_executor_node)
    workflow.add_node("error_analyzer", error_analyzer_node)
    workflow.add_node("code_repair", code_repair_node)
    workflow.add_node("final_reporter", final_reporter_node)

    workflow.add_edge(START, "requirement_analyzer")
    workflow.add_edge("requirement_analyzer", "planner")
    workflow.add_edge("planner", "approval_handler")

    workflow.add_conditional_edges(
        "approval_handler",
        route_after_approval,
        {
            "code_generator": "code_generator",
            "final_reporter": "final_reporter",
        },
    )

    workflow.add_edge("code_generator", "code_executor")
    workflow.add_edge("code_executor", "error_analyzer")

    workflow.add_conditional_edges(
        "error_analyzer",
        route_after_error_analysis,
        {
            "code_repair": "code_repair",
            "final_reporter": "final_reporter",
        },
    )

    workflow.add_edge("code_repair", "code_executor")
    workflow.add_edge("final_reporter", END)

    return workflow


async def get_sqlite_checkpointer(db_path: Optional[str] = None) -> AsyncSqliteSaver:
    settings = get_settings()
    path = db_path or settings.checkpoint_db_path
    connection = await aiosqlite.connect(path)
    saver = AsyncSqliteSaver(connection)
    await saver.setup()
    return saver


async def create_compiled_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> CompiledStateGraph:
    workflow = build_agent_graph()
    actual_checkpointer = checkpointer or await get_sqlite_checkpointer()
    return workflow.compile(
        checkpointer=actual_checkpointer,
        interrupt_before=["code_generator"],
    )
