import json
from pathlib import Path
from typing import Any, Dict, Optional
from app.agent.graph import create_compiled_graph
from app.agent.state import create_initial_agent_state
from app.core.config import get_settings
from app.services.session_service import SessionService
from app.services.websocket_manager import get_websocket_manager


class AgentOrchestratorService:
    def __init__(self, session_service: SessionService) -> None:
        self._session_service = session_service
        self._ws_manager = get_websocket_manager()

    async def _sync_state_to_db(self, session_id: str, state: Dict[str, Any]) -> None:
        final_summary_str = (
            json.dumps(state["final_summary"])
            if state.get("final_summary")
            else None
        )
        await self._session_service.update_session(
            session_id=session_id,
            status=state.get("final_status") or state.get("current_step", "in_progress"),
            current_step=state.get("current_step"),
            approval_status=state.get("approval_status"),
            repair_attempts=state.get("repair_attempts", 0),
            final_summary=final_summary_str,
        )

        for gen_file in state.get("generated_files", []):
            await self._session_service.record_file_metadata(
                session_id=session_id,
                file_path=gen_file["path"],
                file_type="code",
                action="created",
                size_bytes=gen_file.get("size_bytes", 0),
            )

        for mod_file in state.get("modified_files", []):
            await self._session_service.record_file_metadata(
                session_id=session_id,
                file_path=mod_file["path"],
                file_type="code",
                action="modified",
                size_bytes=mod_file.get("size_bytes", 0),
            )

        for exec_entry in state.get("execution_history", []):
            await self._session_service.record_execution(
                session_id=session_id,
                step_name="code_execution",
                command=exec_entry.get("command"),
                exit_code=exec_entry.get("exit_code"),
                output=(exec_entry.get("stdout", "") + "\n" + exec_entry.get("stderr", "")).strip(),
            )

    async def run_agent(
        self,
        session_id: str,
        task_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        session_obj = await self._session_service.get_session(session_id)
        if not session_obj:
            raise ValueError(f"Session not found: {session_id}")

        effective_task = task_description or session_obj.task_description
        initial_state = create_initial_agent_state(session_id, effective_task)

        await self._ws_manager.broadcast_session_event(
            session_id=session_id,
            event="agent.started",
            payload={"session_id": session_id, "task": effective_task},
        )

        graph = await create_compiled_graph()
        config = {"configurable": {"thread_id": session_id}}

        result = await graph.ainvoke(initial_state, config=config)
        await self._sync_state_to_db(session_id, result)
        return result

    async def approve_plan(
        self,
        session_id: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        await self._session_service.record_approval(
            session_id=session_id,
            decision="approved",
            feedback=feedback,
        )

        graph = await create_compiled_graph()
        config = {"configurable": {"thread_id": session_id}}

        await graph.aupdate_state(config, {"approval_status": "approved"})
        result = await graph.ainvoke(None, config=config)
        await self._sync_state_to_db(session_id, result)
        return result

    async def reject_plan(
        self,
        session_id: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        await self._session_service.record_approval(
            session_id=session_id,
            decision="rejected",
            feedback=feedback,
        )

        graph = await create_compiled_graph()
        config = {"configurable": {"thread_id": session_id}}

        await graph.aupdate_state(config, {"approval_status": "rejected"})
        result = await graph.ainvoke(None, config=config)
        await self._sync_state_to_db(session_id, result)
        return result

    async def continue_agent(
        self,
        session_id: str,
        instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        graph = await create_compiled_graph()
        config = {"configurable": {"thread_id": session_id}}

        if instruction:
            await graph.aupdate_state(config, {"task_description": instruction})

        result = await graph.ainvoke(None, config=config)
        await self._sync_state_to_db(session_id, result)
        return result

    async def get_agent_status(self, session_id: str) -> Dict[str, Any]:
        session_obj = await self._session_service.get_session(session_id)
        if not session_obj:
            raise ValueError(f"Session not found: {session_id}")

        graph = await create_compiled_graph()
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await graph.aget_state(config)

        if snapshot and snapshot.values:
            current_values = snapshot.values
            return {
                "session_id": session_id,
                "status": current_values.get("final_status", session_obj.status),
                "current_step": current_values.get("current_step", session_obj.current_step),
                "approval_status": current_values.get("approval_status", session_obj.approval_status),
                "repair_attempts": current_values.get("repair_attempts", session_obj.repair_attempts),
                "final_summary": current_values.get("final_summary") or session_obj.final_summary,
            }

        return {
            "session_id": session_id,
            "status": session_obj.status,
            "current_step": session_obj.current_step,
            "approval_status": session_obj.approval_status,
            "repair_attempts": session_obj.repair_attempts,
            "final_summary": session_obj.final_summary,
        }

    async def get_restored_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        session_obj = await self._session_service.get_session(session_id)
        if not session_obj:
            return None

        history_records = await self._session_service.get_execution_history(session_id)
        execution_history = [
            {
                "command": h.command,
                "exit_code": h.exit_code,
                "stdout": h.output,
                "stderr": "",
                "step_name": h.step_name,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history_records
        ]

        graph = await create_compiled_graph()
        config = {"configurable": {"thread_id": session_id}}
        snapshot = await graph.aget_state(config)
        snapshot_values = snapshot.values if snapshot and snapshot.values else {}

        settings = get_settings()
        workspace_dir = Path(settings.workspace_base_path).resolve() / session_id
        files = []
        if workspace_dir.exists():
            for item in workspace_dir.rglob("*"):
                if item.is_file():
                    if any(part.startswith(".") or part == "__pycache__" for part in item.parts):
                        continue
                    try:
                        content = item.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        content = ""
                    files.append({
                        "path": str(item.relative_to(workspace_dir)),
                        "name": item.name,
                        "size": item.stat().st_size,
                        "content": content,
                    })
            files.sort(key=lambda x: x["path"])

        is_awaiting_approval = (
            session_obj.current_step == "awaiting_approval"
            or session_obj.status == "awaiting_approval"
            or (bool(snapshot and "code_generator" in getattr(snapshot, "next", [])) and session_obj.approval_status == "pending")
        )

        final_summary = snapshot_values.get("final_summary")
        if not final_summary and session_obj.final_summary:
            try:
                final_summary = json.loads(session_obj.final_summary)
            except Exception:
                final_summary = session_obj.final_summary

        return {
            "session_id": session_id,
            "status": snapshot_values.get("final_status") or session_obj.status,
            "current_step": snapshot_values.get("current_step") or session_obj.current_step,
            "approval_status": snapshot_values.get("approval_status") or session_obj.approval_status,
            "repair_attempts": snapshot_values.get("repair_attempts", session_obj.repair_attempts),
            "final_summary": final_summary,
            "requirements": snapshot_values.get("requirements"),
            "plan": snapshot_values.get("implementation_plan"),
            "test_results": snapshot_values.get("test_results"),
            "execution_history": execution_history,
            "files": files,
            "approval_required": is_awaiting_approval,
        }
