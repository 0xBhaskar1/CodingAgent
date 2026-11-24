from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionAuditEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    operation: str
    target: str
    status: str
    exit_code: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExecutionAuditLogger:
    _instance: Optional["ExecutionAuditLogger"] = None

    def __init__(self) -> None:
        self._entries: List[ExecutionAuditEntry] = []

    @classmethod
    def get_logger(cls) -> "ExecutionAuditLogger":
        if cls._instance is None:
            cls._instance = ExecutionAuditLogger()
        return cls._instance

    def log(
        self,
        session_id: str,
        operation: str,
        target: str,
        status: str,
        exit_code: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_seconds: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExecutionAuditEntry:
        entry = ExecutionAuditEntry(
            session_id=session_id,
            operation=operation,
            target=target,
            status=status,
            exit_code=exit_code,
            error_type=error_type,
            error_message=error_message,
            duration_seconds=duration_seconds,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        return entry

    def get_entries_for_session(self, session_id: str) -> List[ExecutionAuditEntry]:
        return [entry for entry in self._entries if entry.session_id == session_id]

    def clear(self) -> None:
        self._entries.clear()
