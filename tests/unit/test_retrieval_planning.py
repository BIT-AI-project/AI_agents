from autoanalyst.retrieval.tool_retriever import ToolRetriever
from autoanalyst.retrieval.tool_registry import build_registry
from autoanalyst.planning.planner import create_plan
from autoanalyst.llm.fake_client import FakeLLM

def test_retriever_scores_python_chart(config,tmp_path):
    docs=build_registry(config.dataset_path,tmp_path,config).summaries()
    results=ToolRetriever(docs,top_k=2).retrieve("create a python visualization chart")
    assert results and results[0]["name"]=="python_execute"

def test_retrieval_fallback(config,tmp_path):
    docs=build_registry(config.dataset_path,tmp_path,config).summaries()
    results=ToolRetriever(docs,top_k=3).retrieve("zzqqvvcx")
    assert {x["name"] for x in results}=={"sql_schema_inspect","sql_query","python_execute"}

def test_planner_validated():
    plan=create_plan(FakeLLM(),"compare sales","sales_facts available",[])
    assert 1<=len(plan.steps)<=8

def test_planner_invalid_json_fallback():
    class Bad:
        def complete_json(self,*args,**kwargs): return {"steps":[{"invalid":True}]}
    plan=create_plan(Bad(),"x","y",[])
    assert plan.metadata.get("fallback") is True
