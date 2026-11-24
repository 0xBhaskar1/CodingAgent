from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    task_description: str = Field(..., min_length=1)


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    task_description: str
    status: str
    current_step: Optional[str] = None
    approval_status: str
    repair_attempts: int
    final_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SessionStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    status: str
    current_step: Optional[str] = None
    approval_status: str
    repair_attempts: int
    final_summary: Optional[str] = None
