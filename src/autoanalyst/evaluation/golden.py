"""Dataset-backed assertions used by evaluation runs."""
from pathlib import Path
import sqlite3

def check_artifacts(question, result):
    failures=[]
    expected=question.get("expected_artifacts",[])
    if "report" in expected and not (result.get("report_file") and Path(result["report_file"]).exists()): failures.append("missing_report")
    if "chart" in expected and not result.get("chart_files"): failures.append("missing_chart")
    for chart in result.get("chart_files",[]):
        if not Path(chart).exists() or Path(chart).stat().st_size==0: failures.append(f"invalid_chart:{chart}")
    return failures

def dataset_reference(db_path, question):
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM sales_facts").fetchone()[0] > 0

def validate_golden_references(db_path, golden_path):
    """Check committed reference values against the licensed local source DB."""
    import json
    checks=json.loads(Path(golden_path).read_text(encoding="utf-8"))["checks"]
    failures=[]
    with sqlite3.connect(db_path) as conn:
        for item in checks:
            count,revenue=conn.execute(item["reference_sql"],(item["entity_name"],)).fetchone()
            expected_count=item.get("expected_source_rows",item.get("expected_order_detail_rows",item.get("expected_invoice_line_rows")))
            expected_revenue=item.get("expected_lifetime_net_revenue_gbp",item.get("expected_lifetime_revenue"))
            tolerance=item.get("absolute_tolerance_gbp",item.get("absolute_tolerance",0.01))
            if count!=expected_count or abs(revenue-expected_revenue)>tolerance:
                failures.append(item["question_id"])
    return {"checks":len(checks),"failures":failures,"valid":not failures}
