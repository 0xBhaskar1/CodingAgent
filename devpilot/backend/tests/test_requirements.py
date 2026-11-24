import pytest
from pydantic import ValidationError
from app.agent.nodes.analyzer import requirement_analyzer_node
from app.agent.state import create_initial_agent_state
from app.schemas.agent import RequirementsSchema


def test_requirements_schema_validation_success() -> None:
    data = {
        "project_objective": "Build user auth service",
        "functional_requirements": ["Login", "Register"],
        "technical_requirements": ["FastAPI", "JWT"],
        "required_files": ["auth.py"],
        "dependencies": ["pyjwt"],
        "testing_requirements": ["Test JWT encoding"],
    }
    req = RequirementsSchema(**data)
    assert req.project_objective == "Build user auth service"
    assert len(req.functional_requirements) == 2
    assert "auth.py" in req.required_files


def test_requirements_schema_missing_objective_raises() -> None:
    with pytest.raises(ValidationError):
        RequirementsSchema.model_validate({})


@pytest.mark.asyncio
async def test_requirement_analyzer_node_execution() -> None:
    state = create_initial_agent_state("test-session-req", "Create a calculation service")
    result = await requirement_analyzer_node(state)

    assert "requirements" in result
    assert result["current_step"] == "analysis_completed"
    assert "project_objective" in result["requirements"]
    assert len(result["requirements"]["required_files"]) > 0
