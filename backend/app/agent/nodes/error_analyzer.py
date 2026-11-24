from typing import Any, Dict, List
from app.agent.prompts.templates import ERROR_ANALYSIS_PROMPT
from app.agent.state import AgentState
from app.core.config import get_settings
from app.schemas.agent import ErrorAnalysisSchema
from app.services.llm_provider import LLMProviderFactory
from app.services.websocket_manager import get_websocket_manager


async def error_analyzer_node(state: AgentState) -> Dict[str, Any]:
    settings = get_settings()
    llm = LLMProviderFactory.create_provider(settings)
    ws_manager = get_websocket_manager()

    test_results = state.get("test_results", {})
    success = bool(test_results.get("success", False))
    error_logs: List[str] = list(state.get("error_logs", []))
    session_id = state["session_id"]

    if success:
        await ws_manager.broadcast_session_event(
            session_id=session_id,
            event="tests.passed",
            payload=test_results,
        )
        return {
            "current_step": "analysis_success",
            "error_logs": error_logs,
        }

    prompt = ERROR_ANALYSIS_PROMPT.format(
        command=test_results.get("command", "unknown"),
        exit_code=test_results.get("exit_code", -1),
        stdout=test_results.get("stdout", "")[:1000],
        stderr=test_results.get("stderr", "")[:1000],
    )

    analysis = await llm.generate_structured(
        prompt=prompt,
        schema_class=ErrorAnalysisSchema,
    )

    if analysis.failure_summary:
        error_logs.append(analysis.failure_summary)
    elif test_results.get("stderr"):
        error_logs.append(test_results["stderr"])

    fail_payload = {
        "failure_summary": analysis.failure_summary,
        "root_cause": analysis.root_cause,
        "failing_files": analysis.failing_files,
        "exit_code": test_results.get("exit_code"),
        "stderr": test_results.get("stderr"),
    }

    await ws_manager.broadcast_session_event(
        session_id=session_id,
        event="tests.failed",
        payload=fail_payload,
    )

    return {
        "current_step": "analysis_failed",
        "error_logs": error_logs,
    }
