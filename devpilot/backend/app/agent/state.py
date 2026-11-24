from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict):
    session_id: str
    task_description: str
    requirements: Dict[str, Any]
    implementation_plan: List[Dict[str, Any]]
    current_step: str
    generated_files: List[Dict[str, Any]]
    modified_files: List[Dict[str, Any]]
    execution_history: List[Dict[str, Any]]
    test_results: Dict[str, Any]
    error_logs: List[str]
    repair_attempts: int
    approval_status: str
    final_status: str
    final_summary: Dict[str, Any]


def create_initial_agent_state(session_id: str, task_description: str) -> AgentState:
    return {
        "session_id": session_id,
        "task_description": task_description,
        "requirements": {},
        "implementation_plan": [],
        "current_step": "initialized",
        "generated_files": [],
        "modified_files": [],
        "execution_history": [],
        "test_results": {},
        "error_logs": [],
        "repair_attempts": 0,
        "approval_status": "pending",
        "final_status": "in_progress",
        "final_summary": {},
    }
