from autoanalyst.config import AppConfig
from autoanalyst.state.models import AgentState, Plan, PlanStep

def test_mode_flags():
    cfg=AppConfig().with_mode("react_baseline")
    assert not cfg.planning_enabled and not cfg.output_review_enabled and not cfg.tool_retrieval_enabled
    assert AppConfig().with_mode("plan_with_review").output_review_enabled

def test_yaml_configuration_loads_default():
    from pathlib import Path
    cfg=AppConfig.load(Path(__file__).resolve().parents[2]/"configs"/"default.yaml")
    assert cfg.dataset_path.name=="online_retail.sqlite" and cfg.top_k_tools==4

def test_state_and_plan_are_json_serializable():
    state=AgentState(run_id="r",user_query="sales")
    assert state.model_dump(mode="json")["status"]=="pending"
    plan=Plan(steps=[PlanStep(step_id="1",objective="query",expected_output="rows",success_criteria="rows returned")])
    assert plan.model_dump(mode="json")["steps"][0]["step_id"]=="1"
