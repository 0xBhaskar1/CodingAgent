from typing import Any, Dict
from app.agent.prompts.templates import REQUIREMENTS_ANALYSIS_PROMPT
from app.agent.state import AgentState
from app.core.config import get_settings
from app.schemas.agent import RequirementsSchema
from app.services.llm_provider import LLMProviderFactory
from app.services.websocket_manager import get_websocket_manager


async def requirement_analyzer_node(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    llm = LLMProviderFactory.create_provider(settings)
    ws_manager = get_websocket_manager()

    prompt = REQUIREMENTS_ANALYSIS_PROMPT.format(
        task_description=state["task_description"]
    )
    requirements = await llm.generate_structured(
        prompt=prompt,
        schema_class=RequirementsSchema,
    )

    req_dict = requirements.model_dump()
    await ws_manager.broadcast_session_event(
        session_id=state["session_id"],
        event="analysis.completed",
        payload=req_dict,
    )

    return {
        "requirements": req_dict,
        "current_step": "analysis_completed",
    }
