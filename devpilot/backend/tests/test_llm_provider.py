import pytest
from app.core.config import Settings
from app.schemas.agent import (
    ErrorAnalysisSchema,
    ImplementationPlanSchema,
    RequirementsSchema,
)
from app.services.llm_provider import (
    GeminiLLMProvider,
    LLMProviderFactory,
    MockLLMProvider,
)


@pytest.mark.asyncio
async def test_gemini_missing_api_key_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = GeminiLLMProvider(api_key="", model_name="gemini-2.5-flash")
    with pytest.raises(ValueError) as excinfo:
        await provider.generate_text("Hello")
    assert "GEMINI_API_KEY environment variable is not configured" in str(excinfo.value)


@pytest.mark.asyncio
async def test_gemini_bounded_retry_mechanism() -> None:
    provider = GeminiLLMProvider(
        api_key="mock_key",
        model_name="gemini-2.5-flash",
        max_retries=2,
    )

    call_count = 0

    async def failing_operation():
        nonlocal call_count
        call_count += 1
        raise ConnectionError("Network dropped")

    with pytest.raises(RuntimeError) as excinfo:
        await provider._execute_with_retry(failing_operation)

    assert call_count == 2
    assert "Gemini API invocation failed after 2 attempts" in str(excinfo.value)


@pytest.mark.asyncio
async def test_mock_llm_provider_structured_outputs() -> None:
    mock_provider = MockLLMProvider()

    req = await mock_provider.generate_structured("Task", RequirementsSchema)
    assert isinstance(req, RequirementsSchema)
    assert len(req.required_files) > 0

    plan = await mock_provider.generate_structured("Task", ImplementationPlanSchema)
    assert isinstance(plan, ImplementationPlanSchema)
    assert len(plan.tasks) > 0

    analysis = await mock_provider.generate_structured("Task", ErrorAnalysisSchema)
    assert isinstance(analysis, ErrorAnalysisSchema)
    assert analysis.is_success is True


def test_llm_provider_factory_selection() -> None:
    LLMProviderFactory.reset()
    settings = Settings(default_llm_provider="mock", gemini_api_key="")
    provider = LLMProviderFactory.create_provider(settings)
    assert provider.get_provider_name() == "mock"

    settings_gemini_no_key = Settings(default_llm_provider="gemini", gemini_api_key="")
    provider_fallback = LLMProviderFactory.create_provider(settings_gemini_no_key)
    assert provider_fallback.get_provider_name() == "mock"
