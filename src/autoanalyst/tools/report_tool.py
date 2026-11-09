import re
from pathlib import Path
from autoanalyst.state.models import ToolError, ToolResult
from autoanalyst.reporting.markdown_renderer import render_report

def save_report(args: dict, report_dir: str|Path) -> ToolResult:
    try:
        folder=Path(report_dir).resolve(); folder.mkdir(parents=True,exist_ok=True)
        allowed_root=folder.parent.resolve()
        for chart in args.get("chart_file_paths",[]):
            chart_path=Path(chart).resolve()
            if chart_path!=allowed_root and allowed_root not in chart_path.parents:
                raise ValueError("Chart path escapes the current run output directory")
        title=re.sub(r"[^\w -]","",str(args.get("title","Analysis report")),flags=re.UNICODE).strip()[:80] or "analysis-report"
        path=folder/(re.sub(r"[ -]+","-",title.lower())+".md")
        path.write_text(render_report(args,folder),encoding="utf-8")
        return ToolResult(tool_name="save_markdown_report",status="success",output={"report_file_path":str(path)},artifacts=[str(path)],preview=f"Saved report: {path}")
    except Exception as exc:
        return ToolResult(tool_name="save_markdown_report",status="error",error=ToolError(error_type=type(exc).__name__,error_message=str(exc),suggested_fix="Check output path permissions"),preview=str(exc))
