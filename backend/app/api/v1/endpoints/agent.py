from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db_session
from app.schemas.agent import (
    AgentApprovalRequest,
    AgentContinueRequest,
    AgentRejectRequest,
    AgentRunRequest,
)
from app.services.agent_service import AgentOrchestratorService
from app.services.session_service import SessionService

router = APIRouter()


def get_agent_service(session: AsyncSession = Depends(get_db_session)) -> AgentOrchestratorService:
    session_service = SessionService(session)
    return AgentOrchestratorService(session_service)


@router.post("/{session_id}/run", status_code=status.HTTP_200_OK)
async def run_agent(
    session_id: str,
    payload: AgentRunRequest = AgentRunRequest(),
    service: AgentOrchestratorService = Depends(get_agent_service),
) -> Dict[str, Any]:
    try:
        return await service.run_agent(
            session_id=session_id,
            task_description=payload.task_description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent run execution failed: {str(exc)}",
        )


@router.post("/{session_id}/approve", status_code=status.HTTP_200_OK)
async def approve_agent_plan(
    session_id: str,
    payload: AgentApprovalRequest = AgentApprovalRequest(),
    service: AgentOrchestratorService = Depends(get_agent_service),
) -> Dict[str, Any]:
    try:
        return await service.approve_plan(
            session_id=session_id,
            feedback=payload.feedback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan approval failed: {str(exc)}",
        )


@router.post("/{session_id}/reject", status_code=status.HTTP_200_OK)
async def reject_agent_plan(
    session_id: str,
    payload: AgentRejectRequest = AgentRejectRequest(),
    service: AgentOrchestratorService = Depends(get_agent_service),
) -> Dict[str, Any]:
    try:
        return await service.reject_plan(
            session_id=session_id,
            feedback=payload.feedback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan rejection failed: {str(exc)}",
        )


@router.post("/{session_id}/continue", status_code=status.HTTP_200_OK)
async def continue_agent_execution(
    session_id: str,
    payload: AgentContinueRequest = AgentContinueRequest(),
    service: AgentOrchestratorService = Depends(get_agent_service),
) -> Dict[str, Any]:
    try:
        return await service.continue_agent(
            session_id=session_id,
            instruction=payload.instruction,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent continuation failed: {str(exc)}",
        )


@router.get("/{session_id}/status", status_code=status.HTTP_200_OK)
async def get_agent_status(
    session_id: str,
    service: AgentOrchestratorService = Depends(get_agent_service),
) -> Dict[str, Any]:
    try:
        return await service.get_agent_status(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
