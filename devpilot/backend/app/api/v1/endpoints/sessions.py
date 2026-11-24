from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.database.session import get_db_session
from app.schemas.session import SessionCreate, SessionRead
from app.services.project_service import ProjectService
from app.services.session_service import SessionService

router = APIRouter()


class FileUpdateRequest(BaseModel):
    content: str


def get_session_service(session: AsyncSession = Depends(get_db_session)) -> SessionService:
    return SessionService(session)


def get_project_service(session: AsyncSession = Depends(get_db_session)) -> ProjectService:
    return ProjectService(session)


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    session_service: SessionService = Depends(get_session_service),
    project_service: ProjectService = Depends(get_project_service),
) -> SessionRead:
    project = await project_service.get_project(payload.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {payload.project_id}",
        )
    return await session_service.create_session(payload)


@router.get("", response_model=List[SessionRead])
async def list_sessions(
    project_id: Optional[str] = Query(default=None),
    service: SessionService = Depends(get_session_service),
) -> List[SessionRead]:
    return await service.list_sessions(project_id)


@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionRead:
    session_obj = await service.get_session(session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return session_obj


@router.get("/{session_id}/files")
async def get_session_files(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> List[Dict[str, Any]]:
    session_obj = await service.get_session(session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    settings = get_settings()
    workspace_dir = Path(settings.workspace_base_path).resolve() / session_id
    if not workspace_dir.exists():
        return []

    files_list: List[Dict[str, Any]] = []
    for item in workspace_dir.rglob("*"):
        if item.is_file():
            if any(part.startswith(".") or part == "__pycache__" for part in item.parts):
                continue
            rel_path = str(item.relative_to(workspace_dir))
            try:
                content = item.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
            files_list.append({
                "path": rel_path,
                "name": item.name,
                "size": item.stat().st_size,
                "content": content,
            })
    files_list.sort(key=lambda x: x["path"])
    return files_list


@router.put("/{session_id}/files/{file_path:path}")
async def update_session_file(
    session_id: str,
    file_path: str,
    payload: FileUpdateRequest,
    service: SessionService = Depends(get_session_service),
) -> Dict[str, Any]:
    session_obj = await service.get_session(session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    settings = get_settings()
    workspace_dir = Path(settings.workspace_base_path).resolve() / session_id
    workspace_dir.mkdir(parents=True, exist_ok=True)
    target_file = (workspace_dir / file_path).resolve()
    if not target_file.is_relative_to(workspace_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path outside session workspace",
        )
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(payload.content, encoding="utf-8")
    return {"status": "saved", "path": file_path, "size": target_file.stat().st_size}
