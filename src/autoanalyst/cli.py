"""Run orchestration and command-line application helpers."""
import json, shutil, uuid
from datetime import datetime, timezone
from pathlib import Path
from autoanalyst.config import AppConfig
from autoanalyst.graph.builder import build_graph
from autoanalyst.llm.fake_client import FakeLLM
from autoanalyst.retrieval.tool_registry import build_registry
from autoanalyst.state.models import AgentState

def clean_runs(config) -> int:
    """Delete all previous run folders in <output_dir>/runs. Returns the number of removed entries."""
    runs=(config.output_dir/"runs").resolve()
    if runs.name!="runs" or not runs.is_dir(): return 0
    removed=0
    for entry in runs.iterdir():
        if entry.is_dir(): shutil.rmtree(entry,ignore_errors=True)
        else: entry.unlink(missing_ok=True)
        removed+=1
    return removed

def make_llm(config):
    if config.llm_provider=="fake":
        return FakeLLM()
    if config.llm_provider=="openai":
        if not config.openai_api_key: raise ValueError("llm_provider=openai requires OPENAI_API_KEY or openai_api_key in the config")
        from autoanalyst.llm.openai_client import OpenAICompatibleClient
        model=config.llm_model or config.openai_model
        return OpenAICompatibleClient(config.openai_api_key,model,config.openai_base_url,config.llm_temperature)
    if config.llm_provider=="anthropic":
        if not config.anthropic_api_key: raise ValueError("llm_provider=anthropic requires ANTHROPIC_API_KEY or anthropic_api_key in the config")
        from autoanalyst.llm.anthropic_client import AnthropicJSONClient
        model=config.llm_model or config.anthropic_model
        structured=config.anthropic_structured_outputs
        if structured is None: structured=model.lower().startswith("claude-")
        return AnthropicJSONClient(config.anthropic_api_key,model,config.anthropic_base_url,config.llm_max_tokens,structured)
    if config.llm_provider=="opencode":
        from autoanalyst.llm.opencode_client import OpenCodeJSONClient
        return OpenCodeJSONClient(config.opencode_base_url,config.opencode_token,config.opencode_model or config.llm_model,config.opencode_timeout_seconds)
    raise ValueError(f"Unsupported LLM provider: {config.llm_provider}")

def run_analysis(query: str, config: AppConfig|None=None) -> dict:
    config=config or AppConfig.load()
    if not config.dataset_path.exists(): raise FileNotFoundError(f"Dataset not found at {config.dataset_path}. Run python scripts/fetch_dataset.py then python scripts/prepare_dataset.py")
    run_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
    run_dir=(config.output_dir/"runs"/run_id).resolve(); run_dir.mkdir(parents=True,exist_ok=True)
    llm=make_llm(config); registry=build_registry(config.dataset_path,run_dir,config)
    initial=AgentState(run_id=run_id,user_query=query,workflow_mode=config.workflow_mode,planning_enabled=config.planning_enabled,output_review_enabled=config.output_review_enabled,tool_retrieval_enabled=config.tool_retrieval_enabled,run_dir=str(run_dir)).model_dump(mode="json")
    result=build_graph(registry,config,llm).invoke(initial,config={"recursion_limit":config.max_total_steps*8+30})
    generated=result.get("report_file")
    final=run_dir/"final_report.md"
    if generated and Path(generated).exists():
        shutil.copy2(generated,final)
        content=final.read_text(encoding="utf-8").replace("](../charts/", "](charts/").replace("../charts/", "charts/")
        final.write_text(content,encoding="utf-8")
        result["report_file"]=str(final)
    elif not final.exists():
        from autoanalyst.tools.report_tool import save_report
        fallback=save_report({"title":"AutoAnalyst run diagnostics","executive_summary":"The run could not produce the requested analysis.","sections":[{"heading":"Diagnostics","content":json.dumps(result.get("errors",[]),indent=2)}],"status":"failed"},run_dir)
        if fallback.status=="success": shutil.copy2(fallback.output["report_file_path"],final); result["report_file"]=str(final)
    (run_dir/"state.json").write_text(json.dumps(result,indent=2,default=str),encoding="utf-8")
    (run_dir/"metrics.json").write_text(json.dumps(result.get("metrics",{}),indent=2,default=str),encoding="utf-8")
    if result.get("errors"): (run_dir/"errors.json").write_text(json.dumps(result["errors"],indent=2,default=str),encoding="utf-8")
    result["run_dir"]=str(run_dir)
    return result

def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description="Analyze business data with AutoAnalyst")
    parser.add_argument("--query",required=True); parser.add_argument("--config")
    parser.add_argument("--mode",choices=["react_baseline","plan_only","plan_with_review","plan_with_review_and_retrieval"])
    parser.add_argument("--clean-runs",action="store_true",help="Delete previous run folders in output/runs before running")
    args=parser.parse_args(argv); config=AppConfig.load(args.config)
    if args.mode: config=config.with_mode(args.mode)
    if args.clean_runs: print(f"Removed {clean_runs(config)} previous run(s) from {config.output_dir/'runs'}")
    state=run_analysis(args.query,config)
    provider=state.get("metrics",{}).get("llm_provider",config.llm_provider)
    model=state.get("metrics",{}).get("llm_model") or ("deterministic FakeLLM" if provider=="fake" else "server default")
    print(f"Status: {state.get('status')}\nLLM: {provider} / {model}\nReport: {state.get('report_file')}\nCharts: {', '.join(state.get('chart_files',[])) or 'none'}")
    fallback_count=state.get("metrics",{}).get("llm_fallbacks",0)
    if fallback_count:
        print(f"Warning: {fallback_count} LLM provider call(s) failed; deterministic fallback was used. See {Path(state['run_dir'])/'metrics.json'} for details.")
    if state.get("report_file"):
        import sys
        preview=Path(state["report_file"]).read_text(encoding="utf-8")[:1500]
        encoding=sys.stdout.encoding or "utf-8"
        print("\n"+preview.encode(encoding,errors="replace").decode(encoding))
    else: print("No report generated")

if __name__=="__main__": main()
