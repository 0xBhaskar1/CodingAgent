from pathlib import Path
import pytest
from app.agent.tools.dependency import DependencyInput, DependencyValidationTool
from app.agent.tools.directory import DirectoryListingInput, DirectoryListingTool
from app.agent.tools.filesystem import FileSystemInput, FileSystemTool
from app.agent.tools.pytest_exec import PytestExecutionInput, PytestExecutionTool
from app.agent.tools.python_exec import PythonExecutionInput, PythonExecutionTool
from app.execution.audit import ExecutionAuditLogger
from app.execution.policy import (
    SecurityPolicyError,
    validate_command_and_arguments,
    validate_workspace_path,
)
from app.execution.sandbox import DockerSandboxManager


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "sandbox_ws"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def test_path_traversal_rejection(temp_workspace: Path) -> None:
    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_workspace_path(temp_workspace, "../../etc/passwd")
    assert excinfo.value.error_type == "INVALID_FILE_PATH"

    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_workspace_path(temp_workspace, "/etc/shadow")
    assert excinfo.value.error_type == "INVALID_FILE_PATH"

    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_workspace_path(temp_workspace, "test\0file.py")
    assert excinfo.value.error_type == "INVALID_FILE_PATH"


def test_protected_policy_file_modification_rejected(temp_workspace: Path) -> None:
    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_workspace_path(temp_workspace, "Dockerfile.sandbox")
    assert excinfo.value.error_type == "POLICY_VIOLATION"


def test_unsupported_command_rejected() -> None:
    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_command_and_arguments("bash", ["-c", "echo 1"])
    assert excinfo.value.error_type == "UNSUPPORTED_COMMAND"

    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_command_and_arguments("curl", ["https://example.com"])
    assert excinfo.value.error_type == "UNSUPPORTED_COMMAND"


def test_command_injection_metacharacters_rejected() -> None:
    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_command_and_arguments("python3", ["app.py; rm -rf /"])
    assert excinfo.value.error_type == "UNSUPPORTED_COMMAND"

    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_command_and_arguments("python3", ["$(whoami)"])
    assert excinfo.value.error_type == "UNSUPPORTED_COMMAND"

    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_command_and_arguments("pytest", ["-v", "|", "cat"])
    assert excinfo.value.error_type == "UNSUPPORTED_COMMAND"


def test_privileged_flag_rejected() -> None:
    with pytest.raises(SecurityPolicyError) as excinfo:
        validate_command_and_arguments("python3", ["--privileged", "script.py"])
    assert excinfo.value.error_type == "POLICY_VIOLATION"


@pytest.mark.asyncio
async def test_filesystem_tool_path_traversal(temp_workspace: Path) -> None:
    tool = FileSystemTool(temp_workspace, session_id="sec-fs")
    res = await tool.execute(
        FileSystemInput(
            action="create",
            file_path="../../outside.txt",
            content="hacked",
        )
    )
    assert res.success is False
    assert res.error_type == "INVALID_FILE_PATH"
    assert "Path traversal detected" in (res.error_message or "")


@pytest.mark.asyncio
async def test_filesystem_tool_create_and_read(temp_workspace: Path) -> None:
    tool = FileSystemTool(temp_workspace, session_id="sec-fs-valid")
    res_create = await tool.execute(
        FileSystemInput(
            action="create",
            file_path="src/main.py",
            content="print('secure')",
        )
    )
    assert res_create.success is True
    assert (temp_workspace / "src/main.py").exists()

    res_read = await tool.execute(
        FileSystemInput(
            action="read",
            file_path="src/main.py",
        )
    )
    assert res_read.success is True
    assert res_read.content == "print('secure')"


@pytest.mark.asyncio
async def test_directory_listing_tool_traversal(temp_workspace: Path) -> None:
    tool = DirectoryListingTool(temp_workspace, session_id="sec-dir")
    res = await tool.execute(DirectoryListingInput(directory_path="../../"))
    assert res.success is False
    assert res.error_type == "INVALID_FILE_PATH"


@pytest.mark.asyncio
async def test_dependency_validation_tool(temp_workspace: Path) -> None:
    tool = DependencyValidationTool(temp_workspace, session_id="sec-dep")

    allowed_res = await tool.execute(DependencyInput(package_name="pydantic"))
    assert allowed_res.is_allowed is True

    disallowed_res = await tool.execute(DependencyInput(package_name="malicious_package"))
    assert disallowed_res.is_allowed is False
    assert disallowed_res.error_type == "DISALLOWED_DEPENDENCY"

    injection_res = await tool.execute(DependencyInput(package_name="pydantic; rm -rf /"))
    assert injection_res.is_allowed is False
    assert injection_res.error_type == "DISALLOWED_DEPENDENCY"


@pytest.mark.asyncio
async def test_container_unavailable_fails_explicitly(temp_workspace: Path) -> None:
    broken_sandbox = DockerSandboxManager(image_name="devpilot-sandbox:latest")
    broken_sandbox._runtime_binary = None

    tool = PythonExecutionTool(
        temp_workspace,
        session_id="sec-no-container",
        sandbox_manager=broken_sandbox,
    )
    dummy_script = temp_workspace / "dummy.py"
    dummy_script.write_text("print('test')", encoding="utf-8")

    res = await tool.execute(PythonExecutionInput(script_path="dummy.py"))
    assert res.success is False
    assert res.error_type == "CONTAINER_UNAVAILABLE"
    assert "Container execution engine (Docker/Podman) is unavailable" in (res.error_message or "")


@pytest.mark.asyncio
async def test_execution_timeout_enforced(temp_workspace: Path) -> None:
    sandbox = DockerSandboxManager(image_name="devpilot-sandbox:latest", default_timeout=1)
    if not sandbox.is_available():
        pytest.skip("Container runtime unavailable on host")

    tool = PythonExecutionTool(
        temp_workspace,
        session_id="sec-timeout",
        sandbox_manager=sandbox,
    )
    hang_script = temp_workspace / "hang.py"
    hang_script.write_text("import time\ntime.sleep(10)\n", encoding="utf-8")

    res = await tool.execute(PythonExecutionInput(script_path="hang.py", timeout=1))
    assert res.success is False
    assert res.error_type == "TIMEOUT"
    assert "timed out after 1 seconds" in (res.error_message or "")


@pytest.mark.asyncio
async def test_audit_log_captures_events(temp_workspace: Path) -> None:
    audit_logger = ExecutionAuditLogger.get_logger()
    audit_logger.clear()

    tool = FileSystemTool(temp_workspace, session_id="audit-session")
    await tool.execute(
        FileSystemInput(
            action="create",
            file_path="valid.py",
            content="x = 1",
        )
    )
    await tool.execute(
        FileSystemInput(
            action="read",
            file_path="../../forbidden.txt",
        )
    )

    entries = audit_logger.get_entries_for_session("audit-session")
    assert len(entries) >= 2
    assert any(e.status == "success" for e in entries)
    assert any(e.status == "rejected" and e.error_type == "INVALID_FILE_PATH" for e in entries)
