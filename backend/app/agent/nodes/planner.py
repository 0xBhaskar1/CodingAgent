import json
from typing import Any, Dict
from app.agent.prompts.templates import PLANNER_PROMPT
from app.agent.state import AgentState
from app.core.config import get_settings
from app.schemas.agent import ImplementationPlanSchema
from app.services.llm_provider import LLMProviderFactory
from app.services.websocket_manager import get_websocket_manager


async def planner_node(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    llm = LLMProviderFactory.create_provider(settings)
    ws_manager = get_websocket_manager()

    prompt = PLANNER_PROMPT.format(
        task_description=state["task_description"],
        requirements=json.dumps(state.get("requirements", {})),
    )
    plan = await llm.generate_structured(
        prompt=prompt,
        schema_class=ImplementationPlanSchema,
    )

    plan_tasks = [task.model_dump() for task in plan.tasks]
    await ws_manager.broadcast_session_event(
        session_id=state["session_id"],
        event="plan.generated",
        payload={"overview": plan.overview, "tasks": plan_tasks},
    )

    return {
        "implementation_plan": plan_tasks,
        "current_step": "plan_generated",
    }
