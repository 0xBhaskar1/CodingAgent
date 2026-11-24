import json
from pathlib import Path
from typing import Any, Dict, List
from app.agent.prompts.templates import CODE_GENERATION_PROMPT
from app.agent.state import AgentState
from app.agent.tools.filesystem import FileSystemInput, FileSystemTool
from app.core.config import get_settings
from app.schemas.agent import GeneratedFileSchema
from app.services.llm_provider import LLMProviderFactory
from app.services.websocket_manager import get_websocket_manager


async def code_generator_node(state: AgentState) -> Dict[str, Any]:
    if state.get("approval_status") == "rejected":
        return {
            "current_step": "plan_rejected",
            "generated_files": [],
        }

    settings = get_settings()
    llm = LLMProviderFactory.create_provider(settings)
    ws_manager = get_websocket_manager()

    session_id = state["session_id"]
    base_workspace = Path(settings.workspace_base_path).resolve() / session_id
    base_workspace.mkdir(parents=True, exist_ok=True)

    fs_tool = FileSystemTool(base_workspace, session_id=session_id)

    await ws_manager.broadcast_session_event(
        session_id=session_id,
        event="code.generation.started",
        payload={"session_id": session_id},
    )

    required_files = state.get("requirements", {}).get("required_files", [])
    if not required_files:
        required_files = ["app.py", "test_app.py"]

    generated: List[Dict[str, Any]] = list(state.get("generated_files", []))
    modified: List[Dict[str, Any]] = list(state.get("modified_files", []))

    for target_file in required_files:
        prompt = CODE_GENERATION_PROMPT.format(
            task_description=state["task_description"],
            step_description=f"Generate code for {target_file}",
            target_file=target_file,
            requirements=json.dumps(state.get("requirements", {})),
        )

        file_schema = await llm.generate_structured(
            prompt=prompt,
            schema_class=GeneratedFileSchema,
        )

        relative_path = file_schema.path or target_file
        file_action = "update" if (base_workspace / relative_path).exists() else "create"

        fs_result = await fs_tool.execute(
            FileSystemInput(
                action=file_action,
                file_path=relative_path,
                content=file_schema.content,
            )
        )

        if not fs_result.success:
            continue

        file_entry = {
            "path": fs_result.file_path,
            "content": file_schema.content,
            "action": fs_result.action,
            "size_bytes": fs_result.size_bytes or 0,
        }

        if fs_result.action == "create":
            generated.append(file_entry)
            await ws_manager.broadcast_session_event(
                session_id=session_id,
                event="code.generation.file_created",
                payload={"path": file_entry["path"], "action": "created", "size_bytes": file_entry["size_bytes"]},
            )
            await ws_manager.broadcast_session_event(
                session_id=session_id,
                event="file.created",
                payload={"path": file_entry["path"], "size_bytes": file_entry["size_bytes"]},
            )
        else:
            modified.append(file_entry)
            await ws_manager.broadcast_session_event(
                session_id=session_id,
                event="code.generation.file_created",
                payload={"path": file_entry["path"], "action": "updated", "size_bytes": file_entry["size_bytes"]},
            )
            await ws_manager.broadcast_session_event(
                session_id=session_id,
                event="file.updated",
                payload={"path": file_entry["path"], "size_bytes": file_entry["size_bytes"]},
            )

    await ws_manager.broadcast_session_event(
        session_id=session_id,
        event="code.generation.completed",
        payload={"files": generated + modified},
    )

    return {
        "generated_files": generated,
        "modified_files": modified,
        "current_step": "code_generated",
    }
