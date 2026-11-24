import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.approval import ApprovalDecisionModel
from app.models.execution import ExecutionHistoryModel
from app.models.file_metadata import FileMetadataModel
from app.models.session import SessionModel
from app.schemas.session import SessionCreate


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_session(self, session_id: str) -> Optional[SessionModel]:
        statement = select(SessionModel).where(SessionModel.id == session_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_sessions(self, project_id: Optional[str] = None) -> List[SessionModel]:
        statement = select(SessionModel)
        if project_id:
            statement = statement.where(SessionModel.project_id == project_id)
        statement = statement.order_by(SessionModel.created_at.desc())
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def create_session(self, payload: SessionCreate) -> SessionModel:
        session_id = str(uuid.uuid4())
        session_obj = SessionModel(
            id=session_id,
            project_id=payload.project_id,
            task_description=payload.task_description,
            status="created",
            current_step="initialized",
            approval_status="pending",
            repair_attempts=0,
            final_summary=None,
        )
        self._session.add(session_obj)
        await self._session.commit()
        await self._session.refresh(session_obj)
        return session_obj

    async def update_session(
        self,
        session_id: str,
        status: Optional[str] = None,
        current_step: Optional[str] = None,
        approval_status: Optional[str] = None,
        repair_attempts: Optional[int] = None,
        final_summary: Optional[str] = None,
    ) -> Optional[SessionModel]:
        session_obj = await self.get_session(session_id)
        if not session_obj:
            return None

        if status is not None:
            session_obj.status = status
        if current_step is not None:
            session_obj.current_step = current_step
        if approval_status is not None:
            session_obj.approval_status = approval_status
        if repair_attempts is not None:
            session_obj.repair_attempts = repair_attempts
        if final_summary is not None:
            session_obj.final_summary = final_summary

        await self._session.commit()
        await self._session.refresh(session_obj)
        return session_obj

    async def record_approval(
        self,
        session_id: str,
        decision: str,
        feedback: Optional[str] = None,
    ) -> ApprovalDecisionModel:
        record = ApprovalDecisionModel(
            session_id=session_id,
            decision=decision,
            feedback=feedback,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def record_execution(
        self,
        session_id: str,
        step_name: str,
        command: Optional[str],
        exit_code: Optional[int],
        output: Optional[str],
    ) -> ExecutionHistoryModel:
        record = ExecutionHistoryModel(
            session_id=session_id,
            step_name=step_name,
            command=command,
            exit_code=exit_code,
            output=output,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def get_execution_history(self, session_id: str) -> List[ExecutionHistoryModel]:
        statement = (
            select(ExecutionHistoryModel)
            .where(ExecutionHistoryModel.session_id == session_id)
            .order_by(ExecutionHistoryModel.created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def record_file_metadata(
        self,
        session_id: str,
        file_path: str,
        file_type: str,
        action: str,
        size_bytes: int,
    ) -> FileMetadataModel:
        record = FileMetadataModel(
            session_id=session_id,
            file_path=file_path,
            file_type=file_type,
            action=action,
            size_bytes=size_bytes,
        )
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def get_file_metadata(self, session_id: str) -> List[FileMetadataModel]:
        statement = (
            select(FileMetadataModel)
            .where(FileMetadataModel.session_id == session_id)
            .order_by(FileMetadataModel.created_at.asc())
        )
        result = await self._session.execute(statement)
        return list(result.scalars().all())
