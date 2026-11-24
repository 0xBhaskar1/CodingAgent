from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.services.websocket_manager import WebSocketManager, get_websocket_manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    manager: WebSocketManager = Depends(get_websocket_manager),
) -> None:
    await manager.connect(websocket)
    try:
        await manager.send_personal_message(
            websocket,
            {
                "type": "connection_established",
                "payload": {"message": "DevPilot WebSocket connected successfully"},
            },
        )
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type", "unknown")
            if message_type == "ping":
                await manager.send_personal_message(
                    websocket,
                    {"type": "pong", "payload": {"status": "alive"}},
                )
            else:
                await manager.broadcast(
                    {"type": "message_received", "payload": data},
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
