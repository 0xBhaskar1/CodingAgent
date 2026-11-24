from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from app.execution.policy import SecurityPolicyError, validate_workspace_path
from app.execution.sandbox import DockerSandboxManager, SandboxExecutionResult


class PythonExecutionInput(BaseModel):
    script_path: str = Field(..., description="Relative path to python script within workspace")
    arguments: List[str] = Field(default_factory=list, description="Command line arguments for script")
    timeout: Optional[int] = Field(default=None, description="Execution timeout in seconds")


class PythonExecutionOutput(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class PythonExecutionTool:
    def __init__(
        self,
        workspace_path: Path,
        session_id: str = "default_session",
        sandbox_manager: Optional[DockerSandboxManager] = None,
    ) -> None:
        self._workspace = workspace_path.resolve()
        self._session_id = session_id
        self._sandbox = sandbox_manager or DockerSandboxManager()

    async def execute(self, payload: PythonExecutionInput) -> PythonExecutionOutput:
        try:
            target_script = validate_workspace_path(self._workspace, payload.script_path)
        except SecurityPolicyError as error:
            return PythonExecutionOutput(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error.message,
                duration_seconds=0.0,
                error_type=error.error_type,
                error_message=error.message,
            )

        if not target_script.exists():
            msg = f"Script '{payload.script_path}' does not exist"
            return PythonExecutionOutput(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=msg,
                duration_seconds=0.0,
                error_type="INVALID_FILE_PATH",
                error_message=msg,
            )

        relative_script_str = str(target_script.relative_to(self._workspace))
        result: SandboxExecutionResult = await self._sandbox.execute(
            session_id=self._session_id,
            workspace_dir=self._workspace,
            command="python3",
            args=[relative_script_str, *payload.arguments],
            timeout=payload.timeout,
        )

        return PythonExecutionOutput(
            success=result.success,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_seconds=result.duration_seconds,
            error_type=result.error_type,
            error_message=result.error_message,
        )
