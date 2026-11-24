from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.database.session import async_session_factory
from app.services.agent_service import AgentOrchestratorService
from app.services.session_service import SessionService
from app.services.websocket_manager import WebSocketManager, get_websocket_manager

router = APIRouter()


@router.websocket("/ws/agent/{session_id}")
async def agent_websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    manager: WebSocketManager = Depends(get_websocket_manager),
) -> None:
    await manager.connect_session(session_id, websocket)
    try:
        await manager.send_personal_message(
            websocket,
            {
                "event": "connection_established",
                "session_id": session_id,
                "payload": {"message": f"Connected to session stream: {session_id}"},
            },
        )

        async with async_session_factory() as db_session:
            session_service = SessionService(db_session)
            orchestrator = AgentOrchestratorService(session_service)
            restored_state = await orchestrator.get_restored_session_state(session_id)
            if restored_state:
                await manager.send_personal_message(
                    websocket,
                    {
                        "event": "session.restored",
                        "session_id": session_id,
                        "payload": restored_state,
                    },
                )

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "unknown")
            if message_type == "ping":
                await manager.send_personal_message(
                    websocket,
                    {"event": "pong", "session_id": session_id, "payload": {"status": "alive"}},
                )
    except WebSocketDisconnect:
        manager.disconnect_session(session_id, websocket)
