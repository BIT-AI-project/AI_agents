from typing import Any
from pydantic import BaseModel, Field
from autoanalyst.state.models import PlanStep

class PlanOutput(BaseModel):
    steps: list[PlanStep]
    metadata: dict[str, Any] = Field(default_factory=dict)

class ToolSelection(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    expected_output: str = ""

class RecoveryDecision(BaseModel):
    action: str = "retry"
    revised_tool_name: str | None = None
    revised_arguments: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""

class ReportContent(BaseModel):
    title: str
    executive_summary: str
    sections: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
