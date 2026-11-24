import os
import shutil
from pathlib import Path
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from starlette.testclient import TestClient
from app.agent.graph import route_after_error_analysis
from app.agent.state import AgentState
from app.agent.tools.python_exec import PythonExecutionInput, PythonExecutionTool
from app.core.config import get_settings
from app.execution.sandbox import DockerSandboxManager
from app.main import app
from app.schemas.agent import RequirementsSchema
from app.services.llm_provider import (
    GeminiLLMProvider,
    LLMProviderFactory,
    MockLLMProvider,
)


@pytest.mark.asyncio
async def test_scenario_1_successful_code_generation() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post(
            "/api/projects",
            json={"name": "E2E Success App", "description": "Full success test"},
        )
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        session_res = await client.post(
            "/api/sessions",
            json={
                "project_id": project_id,
                "task_description": "Build calculator service with unit tests",
            },
        )
        assert session_res.status_code == 201
        session_id = session_res.json()["id"]

        run_res = await client.post(f"/api/agent/{session_id}/run")
        assert run_res.status_code == 200
        run_data = run_res.json()
        assert run_data["current_step"] == "awaiting_approval"
        assert run_data["approval_status"] == "pending"

        approve_res = await client.post(
            f"/api/agent/{session_id}/approve",
            json={"feedback": "Plan approved, proceed with generation"},
        )
        assert approve_res.status_code == 200
        approve_data = approve_res.json()
        assert approve_data["final_status"] == "completed"

        status_res = await client.get(f"/api/agent/{session_id}/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["status"] == "completed"

        files_res = await client.get(f"/api/sessions/{session_id}/files")
        assert files_res.status_code == 200
        files = files_res.json()
        assert len(files) > 0


@pytest.mark.asyncio
async def test_scenario_2_user_rejects_plan() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post(
            "/api/projects",
            json={"name": "E2E Reject App", "description": "Test rejection"},
        )
        project_id = proj_res.json()["id"]

        session_res = await client.post(
            "/api/sessions",
            json={
                "project_id": project_id,
                "task_description": "Build high-risk utility",
            },
        )
        session_id = session_res.json()["id"]

        run_res = await client.post(f"/api/agent/{session_id}/run")
        assert run_res.status_code == 200
        assert run_res.json()["current_step"] == "awaiting_approval"

        reject_res = await client.post(
            f"/api/agent/{session_id}/reject",
            json={"feedback": "Rejected: unauthorized operation"},
        )
        assert reject_res.status_code == 200
        reject_data = reject_res.json()
        assert reject_data["final_status"] == "rejected"

        status_res = await client.get(f"/api/agent/{session_id}/status")
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "rejected"

        files_res = await client.get(f"/api/sessions/{session_id}/files")
        assert files_res.status_code == 200
        assert len(files_res.json()) == 0


@pytest.mark.asyncio
async def test_scenario_3_invalid_llm_output() -> None:
    provider = MockLLMProvider()
    provider.set_override_response("RequirementsSchema", {"invalid_key": 123})
    with pytest.raises(ValidationError):
        await provider.generate_structured("Task", RequirementsSchema)


@pytest.mark.asyncio
async def test_scenario_4_llm_api_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiLLMProvider(api_key="", model_name="gemini-2.5-flash")
    with pytest.raises(ValueError) as excinfo:
        await provider.generate_text("Hello")
    assert "GEMINI_API_KEY environment variable is not configured" in str(excinfo.value)


@pytest.mark.asyncio
async def test_scenario_5_docker_unavailable(tmp_path: Path) -> None:
    broken_sandbox = DockerSandboxManager()
    broken_sandbox._runtime_binary = None
    tool = PythonExecutionTool(
        tmp_path,
        session_id="docker-unavail-session",
        sandbox_manager=broken_sandbox,
    )
    dummy_script = tmp_path / "dummy.py"
    dummy_script.write_text("print('test')", encoding="utf-8")
    res = await tool.execute(PythonExecutionInput(script_path="dummy.py"))
    assert res.success is False
    assert res.error_type == "CONTAINER_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scenario_6_docker_execution_timeout(tmp_path: Path) -> None:
    sandbox = DockerSandboxManager(default_timeout=1)
    if not sandbox.is_available():
        pytest.skip("Container runtime unavailable on host")
    tool = PythonExecutionTool(
        tmp_path,
        session_id="timeout-session",
        sandbox_manager=sandbox,
    )
    hang_script = tmp_path / "hang.py"
    hang_script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")
    res = await tool.execute(PythonExecutionInput(script_path="hang.py", timeout=1))
    assert res.success is False
    assert res.error_type == "TIMEOUT"


@pytest.mark.asyncio
async def test_scenario_7_generated_code_has_syntax_errors(tmp_path: Path) -> None:
    bad_code = "def broken_code(\n    return 42\n"
    target_file = tmp_path / "broken.py"
    target_file.write_text(bad_code, encoding="utf-8")

    tool = PythonExecutionTool(tmp_path, session_id="syntax-err-session")
    res = await tool.execute(
        PythonExecutionInput(
            script_path="broken.py",
            arguments=[],
            timeout=10,
        )
    )
    assert res.success is False
    assert res.exit_code != 0
    assert "SyntaxError" in (res.stderr or "")


@pytest.mark.asyncio
async def test_scenario_8_tests_fail_and_are_repaired() -> None:
    failed_state: AgentState = {
        "session_id": "repair-test-session",
        "task_description": "Repair test",
        "requirements": {},
        "implementation_plan": [],
        "current_step": "error_analysis",
        "generated_files": [{"path": "app.py", "content": "def run(): return 0"}],
        "modified_files": [],
        "execution_history": [],
        "test_results": {"success": False, "exit_code": 1, "stdout": "", "stderr": "Assert failed"},
        "error_logs": ["Assert failed"],
        "repair_attempts": 0,
        "approval_status": "approved",
        "final_status": "in_progress",
        "final_summary": None,
    }
    next_node = route_after_error_analysis(failed_state)
    assert next_node == "code_repair"

    succeeded_state = dict(failed_state)
    succeeded_state["test_results"] = {"success": True, "exit_code": 0, "stdout": "Passed"}
    next_node_success = route_after_error_analysis(succeeded_state)
    assert next_node_success == "final_reporter"


@pytest.mark.asyncio
async def test_scenario_9_maximum_repair_attempts_reached() -> None:
    maxed_state: AgentState = {
        "session_id": "max-repairs-session",
        "task_description": "Max repair task",
        "requirements": {},
        "implementation_plan": [],
        "current_step": "error_analysis",
        "generated_files": [],
        "modified_files": [],
        "execution_history": [],
        "test_results": {"success": False, "exit_code": 1, "stdout": "", "stderr": "Still failing"},
        "error_logs": ["Still failing"],
        "repair_attempts": 3,
        "approval_status": "approved",
        "final_status": "in_progress",
        "final_summary": None,
    }
    next_node = route_after_error_analysis(maxed_state)
    assert next_node == "final_reporter"


@pytest.mark.asyncio
async def test_scenario_10_websocket_reconnection_preserves_history() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        proj_res = await client.post("/api/projects", json={"name": "WS Project"})
        project_id = proj_res.json()["id"]

        sess_res = await client.post(
            "/api/sessions",
            json={"project_id": project_id, "task_description": "WebSocket recovery task"},
        )
        session_id = sess_res.json()["id"]

        await client.post(f"/api/agent/{session_id}/run")

    sync_client = TestClient(app)
    with sync_client.websocket_connect(f"/ws/agent/{session_id}") as ws1:
        msg1 = ws1.receive_json()
        assert msg1["event"] == "connection_established"
        msg2 = ws1.receive_json()
        assert msg2["event"] == "session.restored"
        assert msg2["payload"]["session_id"] == session_id
        assert msg2["payload"]["current_step"] == "awaiting_approval"
        assert msg2["payload"]["approval_required"] is True

    with sync_client.websocket_connect(f"/ws/agent/{session_id}") as ws2:
        reconnect_msg1 = ws2.receive_json()
        assert reconnect_msg1["event"] == "connection_established"
        reconnect_msg2 = ws2.receive_json()
        assert reconnect_msg2["event"] == "session.restored"
        assert reconnect_msg2["payload"]["session_id"] == session_id
        assert reconnect_msg2["payload"]["current_step"] == "awaiting_approval"
        assert reconnect_msg2["payload"]["approval_required"] is True


@pytest.mark.asyncio
async def test_scenario_11_backend_restart_during_existing_session() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client1:
        proj_res = await client1.post("/api/projects", json={"name": "Restart Project"})
        project_id = proj_res.json()["id"]

        sess_res = await client1.post(
            "/api/sessions",
            json={"project_id": project_id, "task_description": "Restart resilience task"},
        )
        session_id = sess_res.json()["id"]

        run_res = await client1.post(f"/api/agent/{session_id}/run")
        assert run_res.status_code == 200
        assert run_res.json()["current_step"] == "awaiting_approval"

    new_transport = ASGITransport(app=app)
    async with AsyncClient(transport=new_transport, base_url="http://test") as client2:
        status_res = await client2.get(f"/api/agent/{session_id}/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["current_step"] == "awaiting_approval"
        assert status_data["approval_status"] == "pending"

        approve_res = await client2.post(
            f"/api/agent/{session_id}/approve",
            json={"feedback": "Approved after simulated restart"},
        )
        assert approve_res.status_code == 200
        approve_data = approve_res.json()
        assert approve_data["final_status"] == "completed"

        after_restart_status = await client2.get(f"/api/agent/{session_id}/status")
        assert after_restart_status.status_code == 200
        assert after_restart_status.json()["status"] == "completed"
