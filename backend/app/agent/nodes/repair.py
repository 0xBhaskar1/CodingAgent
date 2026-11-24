import json
from pathlib import Path
from typing import Any, Dict, List
from app.agent.prompts.templates import CODE_REPAIR_PROMPT
from app.agent.state import AgentState
from app.agent.tools.filesystem import FileSystemInput, FileSystemTool
from app.core.config import get_settings
from app.schemas.agent import RepairProposalSchema
from app.services.llm_provider import LLMProviderFactory
from app.services.websocket_manager import get_websocket_manager


async def code_repair_node(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    llm = LLMProviderFactory.create_provider(settings)
    ws_manager = get_websocket_manager()

    session_id = state["session_id"]
    current_attempts = state.get("repair_attempts", 0) + 1
    base_workspace = Path(settings.workspace_base_path).resolve() / session_id
    base_workspace.mkdir(parents=True, exist_ok=True)

    fs_tool = FileSystemTool(base_workspace, session_id=session_id)

    await ws_manager.broadcast_session_event(
        session_id=session_id,
        event="repair.started",
        payload={"attempt": current_attempts},
    )

    error_details = json.dumps(state.get("error_logs", []))
    prompt = CODE_REPAIR_PROMPT.format(
        failing_files=json.dumps(state.get("generated_files", [])),
        error_details=error_details,
        existing_code="",
    )

    proposal = await llm.generate_structured(
        prompt=prompt,
        schema_class=RepairProposalSchema,
    )

    modified_files: List[Dict[str, Any]] = list(state.get("modified_files", []))
    for target in proposal.target_files:
        fs_res = await fs_tool.execute(
            FileSystemInput(
                action="update",
                file_path=target.path,
                content=target.content,
            )
        )
        if not fs_res.success:
            continue

        entry = {
            "path": fs_res.file_path,
            "content": target.content,
            "action": "modified",
            "size_bytes": fs_res.size_bytes or len(target.content.encode("utf-8")),
        }
        modified_files.append(entry)

        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="file.updated",
            payload={"path": fs_res.file_path, "size_bytes": entry["size_bytes"]},
        )

    await ws_manager.broadcast_session_event(
        session_id=session_id,
        event="repair.completed",
        payload={"attempt": current_attempts, "explanation": proposal.explanation},
    )

    return {
        "repair_attempts": current_attempts,
        "modified_files": modified_files,
        "current_step": "repair_completed",
    }
