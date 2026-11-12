import argparse
import pathlib
import yaml
from autoanalyst.config import AppConfig
from autoanalyst.evaluation.runner import run_evaluation

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--config",required=False); parser.add_argument("--questions"); parser.add_argument("--limit",type=int); parser.add_argument("--clean-runs",action="store_true",help="Delete previous run folders in output/runs before evaluating")
    args=parser.parse_args(); cfg=AppConfig.load(args.config)
    if args.clean_runs:
        from autoanalyst.cli import clean_runs
        print(f"Removed {clean_runs(cfg)} previous run(s) from {cfg.output_dir/'runs'}")
    if args.limit:
        from pathlib import Path
        import json,tempfile
        source=Path(args.questions or "eval/questions.json"); questions=json.loads(source.read_text(encoding="utf-8"))[:args.limit]
        temp=Path(cfg.output_dir)/"eval_subset.json"; temp.parent.mkdir(parents=True,exist_ok=True); temp.write_text(json.dumps(questions),encoding="utf-8"); args.questions=str(temp)
    raw=yaml.safe_load(pathlib.Path(args.config).read_text(encoding="utf-8")) if args.config else {}
    modes=raw.get("experiment_modes",[]) if raw else []
    if modes:
        label=raw.get("experiment_name","experiment")
        arms={}
        for mode in modes:
            arm_cfg=cfg.with_mode(mode)
            arms[mode]=run_evaluation(arm_cfg,args.questions,label=f"{label}_{mode}")
        root=pathlib.Path(__file__).resolve().parents[2]; out=root/"experiments"/"results"; out.mkdir(parents=True,exist_ok=True)
        import json
        (out/f"{label}.json").write_text(json.dumps({"experiment":label,"arms":arms},indent=2),encoding="utf-8")
        md=[f"# {label.replace('_',' ').title()}","", "| Mode | Success | Avg steps | Tool calls | Mean seconds |", "|---|---:|---:|---:|---:|"]
        md += [f"| {mode} | {m['task_success_rate']:.1%} | {m['average_steps']:.2f} | {m['total_tool_calls']} | {m['average_duration_seconds']:.2f} |" for mode,m in arms.items()]
        (out/f"{label}.md").write_text("\n".join(md),encoding="utf-8")
        print(arms)
    else: print(run_evaluation(cfg,args.questions))
if __name__=="__main__": main()
