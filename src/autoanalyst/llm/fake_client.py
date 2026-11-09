"""Deterministic, offline JSON client for tests and repeatable demos."""
from typing import Any

class FakeLLM:
    usage = {"prompt_tokens":0, "completion_tokens":0}
    def complete_json(self, task: str, payload: dict[str, Any], schema: dict[str, Any] | None = None) -> dict[str, Any]:
        if task in ("tool_selection","tool_selection_retry"):
            return payload.get("recommended_action",{"tool_name":"sql_schema_inspect","arguments":{}})
        if task in ("plan","plan_retry"):
            return {"steps":[
                {"step_id":"s1", "objective":"Inspect available sales data", "expected_output":"Relevant schema", "success_criteria":"sales_facts fields are known", "suggested_tool_hints":["sql_schema_inspect"], "depends_on":[]},
                {"step_id":"s2", "objective":"Query requested business data", "expected_output":"Filtered SQL results", "success_criteria":"Results match requested period and entities", "suggested_tool_hints":["sql_query"], "depends_on":["s1"]},
                {"step_id":"s3", "objective":"Calculate and validate requested metrics", "expected_output":"Analysis summary", "success_criteria":"Metrics are computed from query results", "suggested_tool_hints":["python_execute"], "depends_on":["s2"]},
                {"step_id":"s4", "objective":"Visualize the analysis", "expected_output":"Saved PNG chart", "success_criteria":"Chart file exists", "suggested_tool_hints":["python_execute"], "depends_on":["s3"]},
                {"step_id":"s5", "objective":"Prepare and save the final report", "expected_output":"Markdown report", "success_criteria":"Report and chart links exist", "suggested_tool_hints":["save_markdown_report"], "depends_on":["s4"]}], "metadata":{"source":"deterministic"}}
        if task in ("review","review_retry"):
            result = payload.get("result", {})
            return {"verdict":"pass" if result.get("status")=="success" else "fail", "reason":"Tool returned successfully" if result.get("status")=="success" else "Tool returned an error", "missing_information":[], "corrective_action":None}
        if task in ("recover","recover_retry"): return {"action":"retry", "revised_tool_name":payload.get("tool_name"), "revised_arguments":payload.get("arguments", {}), "explanation":"Retry once after examining the structured failure."}
        return {"tool_name":"sql_schema_inspect", "arguments":{"include_sample_rows":False}, "rationale":"Inspect the dataset before querying.", "expected_output":"Available tables and columns"}
