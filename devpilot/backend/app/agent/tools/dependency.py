from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from app.execution.audit import ExecutionAuditLogger
from app.execution.policy import SecurityPolicyError, validate_dependency_name
from app.execution.sandbox import DockerSandboxManager


class DependencyInput(BaseModel):
    package_name: str = Field(..., description="Name of python package to validate or install")
    version_spec: Optional[str] = Field(default=None, description="Optional version specification")


class DependencyOutput(BaseModel):
    is_allowed: bool
    package_name: str
    installed: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class DependencyValidationTool:
    def __init__(
        self,
        workspace_path: Path,
        session_id: str = "default_session",
        sandbox_manager: Optional[DockerSandboxManager] = None,
    ) -> None:
        self._workspace = workspace_path.resolve()
        self._session_id = session_id
        self._sandbox = sandbox_manager or DockerSandboxManager()
        self._audit_logger = ExecutionAuditLogger.get_logger()

    async def execute(self, payload: DependencyInput) -> DependencyOutput:
        try:
            validated_name = validate_dependency_name(payload.package_name)
        except SecurityPolicyError as error:
            self._audit_logger.log(
                session_id=self._session_id,
                operation="dependency_validation",
                target=payload.package_name,
                status="rejected",
                error_type=error.error_type,
                error_message=error.message,
            )
            return DependencyOutput(
                is_allowed=False,
                package_name=payload.package_name,
                installed=False,
                error_type=error.error_type,
                error_message=error.message,
            )

        full_spec = validated_name
        if payload.version_spec:
            full_spec = f"{validated_name}{payload.version_spec}"

        self._audit_logger.log(
            session_id=self._session_id,
            operation="dependency_validation",
            target=full_spec,
            status="allowed",
        )

        return DependencyOutput(
            is_allowed=True,
            package_name=full_spec,
            installed=True,
        )
