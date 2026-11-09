from typing import Any
from autoanalyst.state.models import Plan
from autoanalyst.planning.schemas import PlanOutput

def create_plan(llm: Any, query: str, dataset_summary: str, reflections: list[str]) -> Plan:
    payload = {"query":query, "dataset_summary":dataset_summary, "capabilities":["read-only SQL", "Python analysis and charts", "Markdown reporting"], "reflections":reflections}
    try:
        raw=llm.complete_json("plan",payload,PlanOutput.model_json_schema())
        return Plan(**PlanOutput.model_validate(raw).model_dump())
    except Exception as first_error:
        try:
            raw=llm.complete_json("plan_retry",{**payload,"correction":"Return a valid JSON object matching the required plan schema."},PlanOutput.model_json_schema())
            return Plan(**PlanOutput.model_validate(raw).model_dump())
        except Exception as retry_error:
            failure=(f"initial attempt: {type(first_error).__name__}: {first_error}; "
                     f"retry: {type(retry_error).__name__}: {retry_error}")[:1200]
        return Plan(steps=[
            {"step_id":"s1", "objective":"Inspect schema", "expected_output":"Relevant columns", "success_criteria":"Known source fields", "suggested_tool_hints":["sql_schema_inspect"]},
            {"step_id":"s2", "objective":"Retrieve and analyze requested data", "expected_output":"Analysis values", "success_criteria":"Answer supported by queried data", "suggested_tool_hints":["sql_query","python_execute"], "depends_on":["s1"]},
            {"step_id":"s3", "objective":"Save report", "expected_output":"Markdown report", "success_criteria":"Report exists", "suggested_tool_hints":["save_markdown_report"], "depends_on":["s2"]}], metadata={"fallback":True,"fallback_reason":locals().get("failure","LLM returned an invalid plan twice")})
