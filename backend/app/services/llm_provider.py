import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel
from app.core.config import Settings
from app.schemas.agent import (
    ErrorAnalysisSchema,
    FinalReportSchema,
    GeneratedFileSchema,
    ImplementationPlanSchema,
    PlanTaskSchema,
    RepairProposalSchema,
    RequirementsSchema,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    @abstractmethod
    def get_provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        raise NotImplementedError


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model_name: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._max_retries = max_retries

    def get_provider_name(self) -> str:
        return "gemini"

    def get_model_name(self) -> str:
        return self._model_name

    async def _execute_with_retry(self, operation: Any) -> Any:
        delay = 1.0
        last_exception: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                return await operation()
            except Exception as exception:
                last_exception = exception
                logger.warning(
                    "Gemini API request failed on attempt %d/%d: %s",
                    attempt + 1,
                    self._max_retries,
                    str(exception),
                )
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2.0
        raise RuntimeError(
            f"Gemini API invocation failed after {self._max_retries} attempts: {last_exception}"
        ) from last_exception

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        api_key = os.getenv("GEMINI_API_KEY") or self._api_key
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is not configured. Configure GEMINI_API_KEY in backend/.env or set DEFAULT_LLM_PROVIDER=mock."
            )

        from google import genai

        client = genai.Client(api_key=api_key)
        config: Dict[str, Any] = {
            "temperature": temperature if temperature is not None else self._temperature,
            "max_output_tokens": max_tokens if max_tokens is not None else self._max_tokens,
        }
        if system_instruction:
            config["system_instruction"] = system_instruction

        async def _call() -> str:
            response = await client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
            return response.text or ""

        return await self._execute_with_retry(_call)

    async def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        instruction = (
            f"{system_instruction}\n" if system_instruction else ""
        ) + f"Return valid JSON matching this schema: {json.dumps(schema_class.model_json_schema())}. Respond with ONLY the raw JSON string."

        raw_response = await self.generate_text(
            prompt=prompt,
            system_instruction=instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        cleaned_text = raw_response.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        cleaned_text = cleaned_text.strip()

        return schema_class.model_validate_json(cleaned_text)


class MockLLMProvider(LLMProvider):
    def __init__(self, model_name: str = "mock-agent-model") -> None:
        self._model_name = model_name
        self._fail_error_analysis: bool = False
        self._override_responses: Dict[str, Any] = {}

    def get_provider_name(self) -> str:
        return "mock"

    def get_model_name(self) -> str:
        return self._model_name

    def set_fail_error_analysis(self, fail: bool) -> None:
        self._fail_error_analysis = fail

    def set_override_response(self, schema_name: str, response: Any) -> None:
        self._override_responses[schema_name] = response

    async def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        return "Mock response generated for prompt: " + prompt[:50]

    async def generate_structured(
        self,
        prompt: str,
        schema_class: Type[T],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        schema_name = schema_class.__name__
        if schema_name in self._override_responses:
            override = self._override_responses[schema_name]
            if isinstance(override, schema_class):
                return override
            if isinstance(override, dict):
                return schema_class.model_validate(override)

        if schema_class is RequirementsSchema:
            return schema_class(
                project_objective="Implement modular solution for: " + prompt[:60],
                functional_requirements=[
                    "Implement core business logic module",
                    "Provide clean API contracts",
                    "Add automated verification tests",
                ],
                technical_requirements=[
                    "Use Python 3.10+ standard libraries and type hints",
                    "Modular structure with single responsibility",
                ],
                required_files=["app.py", "test_app.py"],
                dependencies=["pytest"],
                testing_requirements=["Unit tests verifying valid inputs and edge cases"],
            )

        if schema_class is ImplementationPlanSchema:
            return schema_class(
                overview="Step-by-step implementation plan for software task",
                tasks=[
                    PlanTaskSchema(
                        task_id="TASK-1",
                        description="Create main application implementation in app.py",
                        required_files=["app.py"],
                        dependencies=[],
                        expected_outcome="Functional application core",
                        execution_status="pending",
                    ),
                    PlanTaskSchema(
                        task_id="TASK-2",
                        description="Create unit tests in test_app.py",
                        required_files=["test_app.py"],
                        dependencies=["TASK-1"],
                        expected_outcome="Automated test suite",
                        execution_status="pending",
                    ),
                ],
            )

        if schema_class is GeneratedFileSchema:
            target_name = "app.py"
            lowered = prompt.lower()
            if "target file:\n" in lowered:
                target_name = lowered.split("target file:\n")[1].split("\n")[0].strip()
            elif "target file: " in lowered:
                target_name = lowered.split("target file: ")[1].split("\n")[0].strip()

            if not target_name:
                target_name = "app.py"

            if target_name.startswith("test_") or "test" in target_name:
                return schema_class(
                    path=target_name,
                    content="def test_example():\n    assert True\n",
                    action="created",
                )
            return schema_class(
                path=target_name,
                content="def run_app():\n    return {'status': 'success'}\n",
                action="created",
            )

        if schema_class is ErrorAnalysisSchema:
            if self._fail_error_analysis:
                return schema_class(
                    is_success=False,
                    failure_summary="AssertionError in test_app.py: unexpected return value",
                    failing_files=["app.py"],
                    is_fixable=True,
                    root_cause="Logic branch error in primary compute routine",
                )
            return schema_class(
                is_success=True,
                failure_summary=None,
                failing_files=[],
                is_fixable=True,
                root_cause=None,
            )

        if schema_class is RepairProposalSchema:
            return schema_class(
                explanation="Fix logical defect in calculation function",
                target_files=[
                    GeneratedFileSchema(
                        path="app.py",
                        content="def run_app():\n    return {'status': 'success'}\n",
                        action="modified",
                    )
                ],
            )

        if schema_class is FinalReportSchema:
            return schema_class(
                completed_tasks=["TASK-1", "TASK-2"],
                generated_files=["app.py", "test_app.py"],
                modified_files=[],
                commands_executed=["pytest test_app.py"],
                test_results={"status": "passed", "tests_run": 2, "failures": 0},
                remaining_errors=[],
                repair_attempts=0,
                final_execution_status="success",
            )

        dummy_data: Dict[str, Any] = {}
        for field_name, field_info in schema_class.model_fields.items():
            annotation = field_info.annotation
            if annotation is str:
                dummy_data[field_name] = f"mock_{field_name}"
            elif annotation is int:
                dummy_data[field_name] = 0
            elif annotation is bool:
                dummy_data[field_name] = True
            elif annotation is list or getattr(annotation, "__origin__", None) is list:
                dummy_data[field_name] = []
            elif annotation is dict or getattr(annotation, "__origin__", None) is dict:
                dummy_data[field_name] = {}
            else:
                dummy_data[field_name] = None
        return schema_class.model_validate(dummy_data)


class LLMProviderFactory:
    _instance: Optional[LLMProvider] = None

    @classmethod
    def set_provider(cls, provider: LLMProvider) -> None:
        cls._instance = provider

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @classmethod
    def create_provider(cls, settings: Settings) -> LLMProvider:
        if cls._instance is not None:
            return cls._instance

        provider_name = settings.default_llm_provider.lower().strip()
        if provider_name == "gemini":
            if not settings.gemini_api_key:
                logger.warning(
                    "GEMINI_API_KEY is empty while provider is gemini; defaulting to MockLLMProvider for graceful local execution"
                )
                return MockLLMProvider(model_name=settings.gemini_model)
            return GeminiLLMProvider(
                api_key=settings.gemini_api_key,
                model_name=settings.gemini_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                max_retries=settings.llm_max_retries,
            )

        return MockLLMProvider(model_name=settings.gemini_model)
