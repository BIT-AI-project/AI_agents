"""Markdown report rendering utilities."""
from pathlib import Path
import os

def render_report(args: dict, report_directory: str|Path) -> str:
    folder=Path(report_directory).resolve()
    lines=[f"# {args.get('title','Analysis report')}","", "## Executive summary", "",str(args.get("executive_summary","")),""]
    for section in args.get("sections",[]): lines += [f"## {section.get('heading','Findings')}","",str(section.get("content","")),""]
    for table in args.get("tables",[]): lines += [f"### {table.get('title','Results')}","",str(table.get("markdown","")),""]
    for chart in args.get("chart_file_paths",[]):
        p=Path(chart).resolve()
        try: relative=Path(os.path.relpath(p,folder)).as_posix()
        except ValueError: relative=p.name
        lines += [f"![{p.stem}]({relative})",""]
    for label in ("assumptions","limitations"):
        values=args.get(label,[])
        if values: lines += [f"## {label.title()}",""]+[f"- {value}" for value in values]+[""]
    if args.get("status") not in (None,"completed","success"):
        lines += ["## Status warning","",f"This run completed with status: **{args.get('status')}**. Review diagnostics and source artifacts.",""]
    return "\n".join(lines)
