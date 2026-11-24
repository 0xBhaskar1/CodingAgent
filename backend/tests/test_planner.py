import pytest
from pydantic import ValidationError
from app.agent.nodes.planner import planner_node
from app.agent.state import create_initial_agent_state
from app.schemas.agent import ImplementationPlanSchema, PlanTaskSchema


def test_planner_schema_validation_success() -> None:
    task = PlanTaskSchema(
        task_id="TASK-1",
        description="Implement database connection",
        required_files=["db.py"],
        dependencies=[],
        expected_outcome="Functional connection",
    )
    plan = ImplementationPlanSchema(
        overview="Database integration plan",
        tasks=[task],
    )
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_id == "TASK-1"
    assert plan.tasks[0].execution_status == "pending"


def test_planner_schema_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        PlanTaskSchema.model_validate({"task_id": "TASK-1"})


@pytest.mark.asyncio
async def test_planner_node_execution() -> None:
    state = create_initial_agent_state("test-session-plan", "Implement caching layer")
    state["requirements"] = {
        "project_objective": "Caching service",
        "required_files": ["cache.py", "test_cache.py"],
    }

    result = await planner_node(state)
    assert "implementation_plan" in result
    assert result["current_step"] == "plan_generated"
    assert len(result["implementation_plan"]) > 0
    assert result["implementation_plan"][0]["task_id"] == "TASK-1"
