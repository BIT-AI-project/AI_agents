def after_intake(state): return "plan_task" if state["planning_enabled"] else ("retrieve_tools" if state["tool_retrieval_enabled"] else "choose_next_action")
def after_plan(state): return "retrieve_tools" if state["tool_retrieval_enabled"] else "choose_next_action"
def after_execute(state):
    latest=state.get("tool_outputs",[])[-1] if state.get("tool_outputs") else {}
    if latest.get("status")=="error": return "recover_from_error"
    return "review_tool_output" if state["output_review_enabled"] else "update_plan_if_needed"
def after_review(state):
    verdict=state.get("last_review",{}).get("verdict")
    if verdict=="fail": return "recover_from_error"
    if verdict=="uncertain" and state.get("retry_count_for_current_step",0)<=state.get("max_retries_per_plan_step",2): return "recover_from_error"
    return "update_plan_if_needed"
def after_recovery(state): return "execute_tool" if state.get("selected_tool_name") else "generate_report"
def after_update(state):
    outputs=state.get("tool_outputs",[])
    if outputs and outputs[-1].get("tool_name")=="save_markdown_report": return "finalize_run"
    if state.get("status")=="failed": return "generate_report"
    python_count=sum(1 for output in outputs if output.get("tool_name")=="python_execute")
    expected_python_calls=2 if state.get("planning_enabled") else 1
    if python_count>=expected_python_calls and outputs and outputs[-1].get("tool_name")=="python_execute": return "generate_report"
    return "retrieve_tools" if state.get("tool_retrieval_enabled") else "choose_next_action"
def after_report_prep(state): return "retrieve_tools" if state.get("tool_retrieval_enabled") else "choose_next_action"
