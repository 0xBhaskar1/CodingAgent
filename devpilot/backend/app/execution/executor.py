from pathlib import Path
from typing import List, Optional
from app.execution.audit import ExecutionAuditLogger
from app.execution.sandbox import DockerSandboxManager, SandboxExecutionResult
from app.schemas.agent import ExecutionResultSchema


class SandboxExecutor:
    def __init__(
        self,
        workspace_path: str,
        session_id: str = "default_session",
        use_docker: bool = True,
    ) -> None:
        self._workspace = Path(workspace_path).resolve()
        self._workspace.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id
        self._sandbox_manager = DockerSandboxManager()

    @property
    def workspace(self) -> Path:
        return self._workspace

    async def execute(
        self,
        command: str,
        args: Optional[List[str]] = None,
        timeout: int = 30,
    ) -> ExecutionResultSchema:
        if args is None:
            parts = command.split()
            base_cmd = parts[0] if parts else "python3"
            cmd_args = parts[1:] if len(parts) > 1 else []
        else:
            base_cmd = command
            cmd_args = args

        res: SandboxExecutionResult = await self._sandbox_manager.execute(
            session_id=self._session_id,
            workspace_dir=self._workspace,
            command=base_cmd,
            args=cmd_args,
            timeout=timeout,
        )

        return ExecutionResultSchema(
            command=f"{base_cmd} {' '.join(cmd_args)}",
            exit_code=res.exit_code,
            stdout=res.stdout,
            stderr=res.stderr or (res.error_message or ""),
            success=res.success,
        )
