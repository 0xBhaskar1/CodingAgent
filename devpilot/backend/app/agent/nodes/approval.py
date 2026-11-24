from typing import Any, Dict
from app.agent.state import AgentState
from app.services.websocket_manager import get_websocket_manager


async def approval_handler_node(state: AgentState) -> Dict[str, Any]:
    ws_manager = get_websocket_manager()

    await ws_manager.broadcast_session_event(
        session_id=state["session_id"],
        event="approval.required",
        payload={
            "plan": state.get("implementation_plan", []),
            "current_status": state.get("approval_status", "pending"),
        },
    )

    return {
        "current_step": "awaiting_approval",
    }
