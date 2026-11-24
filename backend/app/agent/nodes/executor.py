from pathlib import Path
from typing import Any, Dict, List
from app.agent.state import AgentState
from app.agent.tools.pytest_exec import PytestExecutionInput, PytestExecutionTool
from app.agent.tools.python_exec import PythonExecutionInput, PythonExecutionTool
from app.core.config import get_settings
from app.services.websocket_manager import get_websocket_manager


async def code_executor_node(state: AgentState) -> Dict[str, Any]:
    if state.get("approval_status") == "rejected":
        return {
            "current_step": "plan_rejected",
        }

    settings = get_settings()
    ws_manager = get_websocket_manager()

    session_id = state["session_id"]
    workspace_dir = Path(settings.workspace_base_path).resolve() / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)

    test_files = list(workspace_dir.glob("test_*.py"))
    if test_files:
        test_tool = PytestExecutionTool(workspace_dir, session_id=session_id)
        command_repr = f"pytest {test_files[0].name}"
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="execution.started",
            payload={"command": command_repr},
        )
        test_out = await test_tool.execute(
            PytestExecutionInput(
                target_path=test_files[0].name,
                arguments=["-v"],
                timeout=30,
            )
        )
        result_dict = {
            "command": command_repr,
            "exit_code": test_out.exit_code,
            "stdout": test_out.stdout,
            "stderr": test_out.stderr or (test_out.error_message or ""),
            "success": test_out.success,
            "error_type": test_out.error_type,
            "error_message": test_out.error_message,
        }
    else:
        py_files = list(workspace_dir.glob("*.py"))
        script_name = py_files[0].name if py_files else "app.py"
        py_tool = PythonExecutionTool(workspace_dir, session_id=session_id)
        command_repr = f"python3 {script_name}"
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="execution.started",
            payload={"command": command_repr},
        )
        py_out = await py_tool.execute(
            PythonExecutionInput(
                script_path=script_name,
                arguments=[],
                timeout=30,
            )
        )
        result_dict = {
            "command": command_repr,
            "exit_code": py_out.exit_code,
            "stdout": py_out.stdout,
            "stderr": py_out.stderr or (py_out.error_message or ""),
            "success": py_out.success,
            "error_type": py_out.error_type,
            "error_message": py_out.error_message,
        }

    history: List[Dict[str, Any]] = list(state.get("execution_history", []))
    history.append(result_dict)

    if result_dict["success"]:
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="execution.completed",
            payload=result_dict,
        )
    else:
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="execution.failed",
            payload=result_dict,
        )

    return {
        "execution_history": history,
        "test_results": result_dict,
        "current_step": "execution_completed",
    }
