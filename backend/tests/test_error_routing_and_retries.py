import pytest
from app.agent.graph import route_after_approval, route_after_error_analysis
from app.agent.nodes.error_analyzer import error_analyzer_node
from app.agent.nodes.repair import code_repair_node
from app.agent.state import create_initial_agent_state


def test_route_after_approval_logic() -> None:
    state_approved = create_initial_agent_state("s1", "task")
    state_approved["approval_status"] = "approved"
    assert route_after_approval(state_approved) == "code_generator"

    state_rejected = create_initial_agent_state("s2", "task")
    state_rejected["approval_status"] = "rejected"
    assert route_after_approval(state_rejected) == "final_reporter"


def test_route_after_error_analysis_success() -> None:
    state = create_initial_agent_state("s3", "task")
    state["test_results"] = {"success": True, "exit_code": 0}
    state["repair_attempts"] = 0
    assert route_after_error_analysis(state) == "final_reporter"


def test_route_after_error_analysis_retry_under_limit() -> None:
    state = create_initial_agent_state("s4", "task")
    state["test_results"] = {"success": False, "exit_code": 1}
    state["repair_attempts"] = 1
    assert route_after_error_analysis(state) == "code_repair"

    state["repair_attempts"] = 2
    assert route_after_error_analysis(state) == "code_repair"


def test_route_after_error_analysis_max_retry_limit() -> None:
    state = create_initial_agent_state("s5", "task")
    state["test_results"] = {"success": False, "exit_code": 1}
    state["repair_attempts"] = 3
    assert route_after_error_analysis(state) == "final_reporter"

    state["repair_attempts"] = 4
    assert route_after_error_analysis(state) == "final_reporter"


@pytest.mark.asyncio
async def test_error_analyzer_node_with_failure() -> None:
    state = create_initial_agent_state("s6", "task")
    state["test_results"] = {
        "success": False,
        "exit_code": 1,
        "command": "pytest test_app.py",
        "stdout": "",
        "stderr": "AssertionError: Expected 200, got 500",
    }
    result = await error_analyzer_node(state)
    assert result["current_step"] == "analysis_failed"
    assert len(result["error_logs"]) > 0


@pytest.mark.asyncio
async def test_code_repair_node_increments_attempts() -> None:
    state = create_initial_agent_state("s7", "task")
    state["repair_attempts"] = 1
    state["error_logs"] = ["AssertionError: Syntax Error"]
    result = await code_repair_node(state)

    assert result["repair_attempts"] == 2
    assert result["current_step"] == "repair_completed"
    assert len(result["modified_files"]) > 0
