import json
from pathlib import Path
from autoanalyst.cli import run_analysis
from autoanalyst.evaluation.golden import check_artifacts, validate_golden_references
from autoanalyst.evaluation.metrics import summarize_runs
from autoanalyst.dataset.validator import validate_dataset

def run_evaluation(config, questions_path=None, output_dir=None, label=None):
    root=Path(__file__).resolve().parents[3]
    questions_path=Path(questions_path or root/"eval"/"questions.json")
    questions=json.loads(questions_path.read_text(encoding="utf-8"))
    validate_dataset(config.dataset_path)
    golden_status=validate_golden_references(config.dataset_path,root/"eval"/"golden"/"checks.json")
    rows=[]
    for q in questions:
        result=run_analysis(q["user_query"],config); metrics=result.get("metrics",{}); failures=check_artifacts(q,result)
        expected=set(q.get("expected_tools",[])); actual={x.get("tool_name") for x in result.get("tool_outputs",[])}
        if not config.planning_enabled: expected.discard("sql_schema_inspect")
        selection=len(expected&actual)/len(expected) if expected else 1.0
        rows.append({**metrics,"question_id":q["id"],"success":bool(metrics.get("success")) and not failures,"artifact_failures":failures,"tool_selection_accuracy":selection,"recoverable_errors":metrics.get("recoverable_errors",sum(1 for e in result.get("errors",[]) if e.get("recoverable",True)))})
    summary=summarize_runs(rows); summary["golden_reference_checks"]=golden_status; output_dir=Path(output_dir or root/"experiments"/"results"); output_dir.mkdir(parents=True,exist_ok=True)
    name=label or config.workflow_mode; (output_dir/f"{name}.json").write_text(json.dumps({"summary":summary,"runs":rows},indent=2),encoding="utf-8")
    md=[f"# Experiment results: {name}","",f"- Tasks: {summary['total_tasks']}",f"- Success rate: {summary['task_success_rate']:.1%}",f"- Mean steps: {summary['average_steps']:.2f}",f"- Total tool calls: {summary['total_tool_calls']}",f"- Mean duration: {summary['average_duration_seconds']:.2f}s","", "## Per-task outcomes", "", "| ID | Success | Steps | Tool calls | Artifact failures |", "|---|---:|---:|---:|---|"]
    md += [f"| {r['question_id']} | {r['success']} | {r.get('total_steps',0)} | {r.get('total_tool_calls',0)} | {', '.join(r['artifact_failures'])} |" for r in rows]
    (output_dir/f"{name}.md").write_text("\n".join(md),encoding="utf-8")
    return summary
