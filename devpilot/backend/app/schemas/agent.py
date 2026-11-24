from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RequirementsSchema(BaseModel):
    project_objective: str
    functional_requirements: List[str] = Field(default_factory=list)
    technical_requirements: List[str] = Field(default_factory=list)
    required_files: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    testing_requirements: List[str] = Field(default_factory=list)


class PlanTaskSchema(BaseModel):
    task_id: str
    description: str
    required_files: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    expected_outcome: str
    execution_status: str = "pending"


class ImplementationPlanSchema(BaseModel):
    overview: str
    tasks: List[PlanTaskSchema] = Field(default_factory=list)


class GeneratedFileSchema(BaseModel):
    path: str
    content: str
    action: str = "created"


class ExecutionResultSchema(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    success: bool


class ErrorAnalysisSchema(BaseModel):
    is_success: bool
    failure_summary: Optional[str] = None
    failing_files: List[str] = Field(default_factory=list)
    is_fixable: bool = True
    root_cause: Optional[str] = None


class RepairProposalSchema(BaseModel):
    explanation: str
    target_files: List[GeneratedFileSchema] = Field(default_factory=list)


class FinalReportSchema(BaseModel):
    completed_tasks: List[str] = Field(default_factory=list)
    generated_files: List[str] = Field(default_factory=list)
    modified_files: List[str] = Field(default_factory=list)
    commands_executed: List[str] = Field(default_factory=list)
    test_results: Dict[str, Any] = Field(default_factory=dict)
    remaining_errors: List[str] = Field(default_factory=list)
    repair_attempts: int = 0
    final_execution_status: str


class AgentRunRequest(BaseModel):
    task_description: Optional[str] = None


class AgentApprovalRequest(BaseModel):
    feedback: Optional[str] = None


class AgentRejectRequest(BaseModel):
    feedback: Optional[str] = None


class AgentContinueRequest(BaseModel):
    instruction: Optional[str] = None


class AgentEventMessage(BaseModel):
    event: str
    session_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str
