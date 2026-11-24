from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import TaskModel
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_tasks(self) -> List[TaskModel]:
        statement = select(TaskModel).order_by(TaskModel.id.desc())
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_task_by_id(self, task_id: int) -> Optional[TaskModel]:
        statement = select(TaskModel).where(TaskModel.id == task_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create_task(self, payload: TaskCreate) -> TaskModel:
        task = TaskModel(
            title=payload.title,
            description=payload.description,
            status="pending",
        )
        self._session.add(task)
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def update_task(self, task_id: int, payload: TaskUpdate) -> Optional[TaskModel]:
        task = await self.get_task_by_id(task_id)
        if not task:
            return None

        if payload.title is not None:
            task.title = payload.title
        if payload.description is not None:
            task.description = payload.description
        if payload.status is not None:
            task.status = payload.status

        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def delete_task(self, task_id: int) -> bool:
        task = await self.get_task_by_id(task_id)
        if not task:
            return False

        await self._session.delete(task)
        await self._session.commit()
        return True
