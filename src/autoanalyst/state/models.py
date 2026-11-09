from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

class PlanStep(BaseModel):
    step_id: str
    objective: str
    expected_output: str
    success_criteria: str
    suggested_tool_hints: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)

class Plan(BaseModel):
    steps: list[PlanStep]
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision: int = 0

class ToolError(BaseModel):
    error_type: str
    error_message: str
    recoverable: bool = True
    suggested_fix: str | None = None
    failed_input_summary: dict[str, Any] | None = None

class ToolResult(BaseModel):
    tool_name: str
    status: Literal["success", "error"]
    output: dict[str, Any] | str = Field(default_factory=dict)
    error: ToolError | None = None
    artifacts: list[str] = Field(default_factory=list)
    preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

class ReviewResult(BaseModel):
    verdict: Literal["pass", "fail", "uncertain"]
    reason: str
    missing_information: list[str] = Field(default_factory=list)
    corrective_action: str | None = None

class AgentState(BaseModel):
    run_id: str
    user_query: str
    normalized_query: str = ""
    dataset_name: str = "UCI Online Retail"
    workflow_mode: str = "plan_with_review_and_retrieval"
    planning_enabled: bool = True
    output_review_enabled: bool = True
    tool_retrieval_enabled: bool = True
    plan: Plan | None = None
    current_plan_step_id: str | None = None
    current_plan_step_index: int = 0
    available_tools: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_tools: list[dict[str, Any]] = Field(default_factory=list)
    selected_tool_name: str | None = None
    selected_tool_args: dict[str, Any] | None = None
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    intermediate_artifacts: list[str] = Field(default_factory=list)
    chart_files: list[str] = Field(default_factory=list)
    report_file: str | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    step_count: int = 0
    tool_call_count: int = 0
    retry_count_for_current_step: int = 0
    recoverable_error_count: int = 0
    recovered_error_count: int = 0
    status: Literal["pending","planning","retrieving_tools","choosing_action","executing_tool","reviewing_output","recovering","reporting","completed","failed"] = "pending"
    metrics: dict[str, Any] = Field(default_factory=dict)
    llm_usage: dict[str, int] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    run_dir: str = ""
    pending_report: dict[str, Any] = Field(default_factory=dict)
    last_review: dict[str, Any] = Field(default_factory=dict)
    consecutive_identical_calls: int = 0
    last_call_fingerprint: str = ""
    recovery_attempted: bool = False
    terminal_failure: bool = False
