from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db_session
from app.schemas.project import ProjectCreate, ProjectRead
from app.services.project_service import ProjectService

router = APIRouter()


def get_project_service(session: AsyncSession = Depends(get_db_session)) -> ProjectService:
    return ProjectService(session)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    return await service.create_project(payload)


@router.get("", response_model=List[ProjectRead])
async def list_projects(
    service: ProjectService = Depends(get_project_service),
) -> List[ProjectRead]:
    return await service.list_projects()


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectRead:
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {project_id}",
        )
    return project
