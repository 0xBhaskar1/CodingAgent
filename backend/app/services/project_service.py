import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import ProjectModel
from app.schemas.project import ProjectCreate


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_projects(self) -> List[ProjectModel]:
        statement = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def get_project(self, project_id: str) -> Optional[ProjectModel]:
        statement = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def create_project(self, payload: ProjectCreate) -> ProjectModel:
        project_id = str(uuid.uuid4())
        project = ProjectModel(
            id=project_id,
            name=payload.name,
            description=payload.description or "",
        )
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return project
