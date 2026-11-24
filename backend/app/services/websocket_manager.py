from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._active_connections: List[WebSocket] = []
        self._session_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        for session_id in list(self._session_connections.keys()):
            if websocket in self._session_connections[session_id]:
                self._session_connections[session_id].remove(websocket)

    async def connect_session(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if session_id not in self._session_connections:
            self._session_connections[session_id] = []
        self._session_connections[session_id].append(websocket)

    def disconnect_session(self, session_id: str, websocket: WebSocket) -> None:
        if session_id in self._session_connections:
            if websocket in self._session_connections[session_id]:
                self._session_connections[session_id].remove(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        for connection in list(self._active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        await websocket.send_json(message)

    async def broadcast_session_event(self, session_id: str, event: str, payload: Dict[str, Any]) -> None:
        message = {
            "event": event,
            "session_id": session_id,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        connections = self._session_connections.get(session_id, [])
        for conn in list(connections):
            try:
                await conn.send_json(message)
            except Exception:
                self.disconnect_session(session_id, conn)

        for conn in list(self._active_connections):
            try:
                await conn.send_json(message)
            except Exception:
                self.disconnect(conn)


websocket_manager = WebSocketManager()


def get_websocket_manager() -> WebSocketManager:
    return websocket_manager
