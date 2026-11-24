from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field
from app.execution.audit import ExecutionAuditLogger
from app.execution.policy import SecurityPolicyError, validate_workspace_path


class DirectoryEntry(BaseModel):
    name: str
    is_directory: bool
    size_bytes: int


class DirectoryListingInput(BaseModel):
    directory_path: str = Field(default=".", description="Relative directory path to list")


class DirectoryListingOutput(BaseModel):
    success: bool
    directory_path: str
    entries: List[DirectoryEntry] = Field(default_factory=list)
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class DirectoryListingTool:
    def __init__(self, workspace_path: Path, session_id: str = "default_session") -> None:
        self._workspace = workspace_path.resolve()
        self._session_id = session_id
        self._audit_logger = ExecutionAuditLogger.get_logger()

    async def execute(self, payload: DirectoryListingInput) -> DirectoryListingOutput:
        try:
            target_dir = validate_workspace_path(self._workspace, payload.directory_path)
        except SecurityPolicyError as error:
            self._audit_logger.log(
                session_id=self._session_id,
                operation="directory_list",
                target=payload.directory_path,
                status="rejected",
                error_type=error.error_type,
                error_message=error.message,
            )
            return DirectoryListingOutput(
                success=False,
                directory_path=payload.directory_path,
                error_type=error.error_type,
                error_message=error.message,
            )

        if not target_dir.exists() or not target_dir.is_dir():
            error_message = f"Directory '{payload.directory_path}' does not exist"
            self._audit_logger.log(
                session_id=self._session_id,
                operation="directory_list",
                target=payload.directory_path,
                status="failed",
                error_type="INVALID_FILE_PATH",
                error_message=error_message,
            )
            return DirectoryListingOutput(
                success=False,
                directory_path=payload.directory_path,
                error_type="INVALID_FILE_PATH",
                error_message=error_message,
            )

        try:
            entries: List[DirectoryEntry] = []
            for item in sorted(target_dir.iterdir()):
                size = item.stat().st_size if item.is_file() else 0
                entries.append(
                    DirectoryEntry(
                        name=item.name,
                        is_directory=item.is_dir(),
                        size_bytes=size,
                    )
                )

            self._audit_logger.log(
                session_id=self._session_id,
                operation="directory_list",
                target=payload.directory_path,
                status="success",
            )
            return DirectoryListingOutput(
                success=True,
                directory_path=payload.directory_path,
                entries=entries,
            )
        except Exception as exception:
            self._audit_logger.log(
                session_id=self._session_id,
                operation="directory_list",
                target=payload.directory_path,
                status="failed",
                error_type="EXECUTION_FAILURE",
                error_message=str(exception),
            )
            return DirectoryListingOutput(
                success=False,
                directory_path=payload.directory_path,
                error_type="EXECUTION_FAILURE",
                error_message=str(exception),
            )
