from typing import Any, Dict
from app.agent.state import AgentState
from app.core.config import get_settings
from app.schemas.agent import FinalReportSchema
from app.services.llm_provider import LLMProviderFactory
from app.services.websocket_manager import get_websocket_manager


async def final_reporter_node(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    llm = LLMProviderFactory.create_provider(settings)
    ws_manager = get_websocket_manager()

    session_id = state["session_id"]
    approval_status = state.get("approval_status", "pending")
    test_results = state.get("test_results", {})
    success = bool(test_results.get("success", False))

    if approval_status == "rejected":
        final_status = "rejected"
    elif success:
        final_status = "completed"
    else:
        final_status = "failed"

    report = await llm.generate_structured(
        prompt=f"Summarize final execution for task: {state.get('task_description', '')}",
        schema_class=FinalReportSchema,
    )

    summary_dict = report.model_dump()
    summary_dict["final_execution_status"] = final_status
    summary_dict["completed_tasks"] = [
        task["task_id"] for task in state.get("implementation_plan", [])
    ]
    summary_dict["generated_files"] = [
        f["path"] for f in state.get("generated_files", [])
    ]
    summary_dict["modified_files"] = [
        f["path"] for f in state.get("modified_files", [])
    ]
    summary_dict["repair_attempts"] = state.get("repair_attempts", 0)

    await ws_manager.broadcast_session_event(
        session_id=session_id,
        event="agent.completed",
        payload={"status": final_status, "summary": summary_dict},
    )

    if final_status == "completed":
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="workflow.completed",
            payload={"summary": summary_dict},
        )
    elif final_status == "rejected":
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="workflow.rejected",
            payload={"summary": summary_dict},
        )
    else:
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="workflow.failed",
            payload={"summary": summary_dict},
        )

    return {
        "final_status": final_status,
        "final_summary": summary_dict,
        "current_step": "completed",
    }
