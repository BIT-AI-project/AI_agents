from typing import Any

def summarize_runs(runs: list[dict[str,Any]]) -> dict[str,Any]:
    total=len(runs); successes=sum(bool(r.get("success")) for r in runs)
    return {"total_tasks":total,"successful_tasks":successes,"task_success_rate":successes/total if total else 0.0,
      "error_recovery_rate":sum(r.get("recovered_errors",0) for r in runs)/max(1,sum(r.get("recoverable_errors",0) for r in runs)),
      "tool_selection_accuracy":sum(r.get("tool_selection_accuracy",0) for r in runs)/total if total else 0.0,
      "average_steps":sum(r.get("total_steps",0) for r in runs)/total if total else 0,
      "total_tool_calls":sum(r.get("total_tool_calls",0) for r in runs),"average_duration_seconds":sum(r.get("duration_seconds",0) for r in runs)/total if total else 0,
      "token_usage":{"prompt_tokens":sum(r.get("token_usage",{}).get("prompt_tokens",0) for r in runs),"completion_tokens":sum(r.get("token_usage",{}).get("completion_tokens",0) for r in runs)}}
