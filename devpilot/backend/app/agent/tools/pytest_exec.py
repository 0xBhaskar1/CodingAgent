import re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from app.execution.policy import SecurityPolicyError, validate_workspace_path
from app.execution.sandbox import DockerSandboxManager, SandboxExecutionResult


class PytestExecutionInput(BaseModel):
    target_path: Optional[str] = Field(default=".", description="Target test file or directory")
    arguments: List[str] = Field(default_factory=list, description="Allowed pytest options")
    timeout: Optional[int] = Field(default=None, description="Test execution timeout in seconds")


class PytestExecutionOutput(BaseModel):
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    tests_run: int
    failures: int
    duration_seconds: float
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class PytestExecutionTool:
    def __init__(
        self,
        workspace_path: Path,
        session_id: str = "default_session",
        sandbox_manager: Optional[DockerSandboxManager] = None,
    ) -> None:
        self._workspace = workspace_path.resolve()
        self._session_id = session_id
        self._sandbox = sandbox_manager or DockerSandboxManager()

    def _parse_test_counts(self, stdout: str) -> tuple[int, int]:
        passed_matches = re.findall(r"(\d+)\s+passed", stdout)
        failed_matches = re.findall(r"(\d+)\s+failed", stdout)
        error_matches = re.findall(r"(\d+)\s+error", stdout)

        passed = int(passed_matches[-1]) if passed_matches else 0
        failed = int(failed_matches[-1]) if failed_matches else 0
        errors = int(error_matches[-1]) if error_matches else 0

        total_failures = failed + errors
        total_run = passed + total_failures
        return total_run, total_failures

    async def execute(self, payload: PytestExecutionInput) -> PytestExecutionOutput:
        target = payload.target_path or "."
        try:
            validated_target = validate_workspace_path(self._workspace, target)
        except SecurityPolicyError as error:
            return PytestExecutionOutput(
                success=False,
                exit_code=-1,
                stdout="",
                stderr=error.message,
                tests_run=0,
                failures=0,
                duration_seconds=0.0,
                error_type=error.error_type,
                error_message=error.message,
            )

        rel_target = str(validated_target.relative_to(self._workspace))
        pytest_args: List[str] = []
        if rel_target != ".":
            pytest_args.append(rel_target)
        pytest_args.extend(payload.arguments)

        result: SandboxExecutionResult = await self._sandbox.execute(
            session_id=self._session_id,
            workspace_dir=self._workspace,
            command="pytest",
            args=pytest_args,
            timeout=payload.timeout,
        )

        tests_run, failures = self._parse_test_counts(result.stdout)

        return PytestExecutionOutput(
            success=result.success,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            tests_run=tests_run,
            failures=failures,
            duration_seconds=result.duration_seconds,
            error_type=result.error_type,
            error_message=result.error_message,
        )
