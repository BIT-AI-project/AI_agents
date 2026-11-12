from pathlib import Path
from autoanalyst.cli import run_analysis

def test_no_matching_rows_finishes_with_explanatory_report(config):
    q="Compare SPOTTY BUNTING and WHITE HANGING HEART T-LIGHT HOLDER sales in Saudi Arabia."
    for mode in ("react_baseline","plan_with_review_and_retrieval"):
        result=run_analysis(q,config.with_mode(mode))
        assert result["status"]=="completed"
        assert not result["chart_files"]
        assert "No matching sales rows" in Path(result["report_file"]).read_text(encoding="utf-8")

def test_end_to_end_plan_review_report_chart(config):
    result=run_analysis("Compare Q3 sales of WHITE HANGING HEART T-LIGHT HOLDER and WHITE METAL LANTERN, and show the best region.",config)
    assert result["status"]=="completed"
    assert result["step_count"]==5
    assert Path(result["report_file"]).exists()
    assert result["chart_files"] and all(Path(p).stat().st_size>0 for p in result["chart_files"])
    assert (Path(result["run_dir"])/"trace.jsonl").exists()
    assert (Path(result["run_dir"])/"metrics.json").exists()

def test_react_mode(config):
    result=run_analysis("Top 5 products by revenue.",config.with_mode("react_baseline"))
    assert result["status"]=="completed"
    assert all(output["tool_name"]!="sql_schema_inspect" for output in result["tool_outputs"])
    assert result["step_count"]==3

def test_read_only_error_recovery_path(config):
    # Explicit recovery helper coverage; SQL tool itself returns a structured failure.
    from autoanalyst.tools.sql_query_tool import execute_query
    failed=execute_query(config.dataset_path,{"query":"SELECT unknown FROM sales_facts"},config.output_dir/"tmp")
    assert failed.status=="error" and failed.error.recoverable

def test_graph_recovers_from_deliberate_sql_tool_error(config):
    from autoanalyst.cli import make_llm
    from autoanalyst.graph.builder import build_graph
    from autoanalyst.retrieval.tool_registry import build_registry
    from autoanalyst.state.models import AgentState, ToolError, ToolResult
    run_dir=config.output_dir/"runs"/"recovery-test"; run_dir.mkdir(parents=True)
    registry=build_registry(config.dataset_path,run_dir,config)
    real=registry.tools["sql_query"].handler; calls={"n":0}
    def fail_once(args):
        calls["n"]+=1
        if calls["n"]==1:
            return ToolResult(tool_name="sql_query",status="error",error=ToolError(error_type="OperationalError",error_message="deliberate test SQL failure"),preview="deliberate test SQL failure")
        return real(args)
    registry.tools["sql_query"].handler=fail_once
    state=AgentState(run_id="recovery-test",user_query="Top products by revenue",run_dir=str(run_dir),workflow_mode=config.workflow_mode,planning_enabled=config.planning_enabled,output_review_enabled=True,tool_retrieval_enabled=config.tool_retrieval_enabled).model_dump(mode="json")
    result=build_graph(registry,config,make_llm(config)).invoke(state,config={"recursion_limit":100})
    assert result["status"]=="completed" and calls["n"]==2
    assert result["metrics"]["recovered_errors"]==1

def test_max_step_limit_finishes_as_failed_with_report(config):
    limited=config.model_copy(update={"max_total_steps":1})
    result=run_analysis("Top 5 products by revenue",limited)
    assert result["status"]=="failed" and Path(result["report_file"]).exists()
