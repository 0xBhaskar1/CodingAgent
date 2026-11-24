from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from app.execution.audit import ExecutionAuditLogger
from app.execution.policy import SecurityPolicyError, validate_workspace_path


class FileSystemInput(BaseModel):
    action: str = Field(..., description="Action to perform: create, read, or update")
    file_path: str = Field(..., description="Relative file path within workspace")
    content: Optional[str] = Field(default=None, description="Content for create or update")


class FileSystemOutput(BaseModel):
    success: bool
    action: str
    file_path: str
    content: Optional[str] = None
    size_bytes: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class FileSystemTool:
    def __init__(self, workspace_path: Path, session_id: str = "default_session") -> None:
        self._workspace = workspace_path.resolve()
        self._session_id = session_id
        self._audit_logger = ExecutionAuditLogger.get_logger()

    async def execute(self, payload: FileSystemInput) -> FileSystemOutput:
        action = payload.action.strip().lower()

        try:
            target_path = validate_workspace_path(self._workspace, payload.file_path)
        except SecurityPolicyError as error:
            self._audit_logger.log(
                session_id=self._session_id,
                operation=f"filesystem_{action}",
                target=payload.file_path,
                status="rejected",
                error_type=error.error_type,
                error_message=error.message,
            )
            return FileSystemOutput(
                success=False,
                action=action,
                file_path=payload.file_path,
                error_type=error.error_type,
                error_message=error.message,
            )

        try:
            if action == "create":
                if payload.content is None:
                    raise ValueError("Content is required when creating a file")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(payload.content, encoding="utf-8")
                size = len(payload.content.encode("utf-8"))

                self._audit_logger.log(
                    session_id=self._session_id,
                    operation="filesystem_create",
                    target=str(target_path.relative_to(self._workspace)),
                    status="success",
                )
                return FileSystemOutput(
                    success=True,
                    action="create",
                    file_path=str(target_path.relative_to(self._workspace)),
                    size_bytes=size,
                )

            elif action == "read":
                if not target_path.exists() or not target_path.is_file():
                    raise FileNotFoundError(f"File '{payload.file_path}' does not exist")
                content = target_path.read_text(encoding="utf-8")
                size = len(content.encode("utf-8"))

                self._audit_logger.log(
                    session_id=self._session_id,
                    operation="filesystem_read",
                    target=str(target_path.relative_to(self._workspace)),
                    status="success",
                )
                return FileSystemOutput(
                    success=True,
                    action="read",
                    file_path=str(target_path.relative_to(self._workspace)),
                    content=content,
                    size_bytes=size,
                )

            elif action == "update":
                if payload.content is None:
                    raise ValueError("Content is required when updating a file")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(payload.content, encoding="utf-8")
                size = len(payload.content.encode("utf-8"))

                self._audit_logger.log(
                    session_id=self._session_id,
                    operation="filesystem_update",
                    target=str(target_path.relative_to(self._workspace)),
                    status="success",
                )
                return FileSystemOutput(
                    success=True,
                    action="update",
                    file_path=str(target_path.relative_to(self._workspace)),
                    size_bytes=size,
                )

            else:
                raise ValueError(f"Unsupported filesystem action: {action}")

        except Exception as exception:
            self._audit_logger.log(
                session_id=self._session_id,
                operation=f"filesystem_{action}",
                target=payload.file_path,
                status="failed",
                error_type="EXECUTION_FAILURE",
                error_message=str(exception),
            )
            return FileSystemOutput(
                success=False,
                action=action,
                file_path=payload.file_path,
                error_type="EXECUTION_FAILURE",
                error_message=str(exception),
            )
