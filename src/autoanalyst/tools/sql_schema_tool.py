import sqlite3
from pathlib import Path
from autoanalyst.state.models import ToolError, ToolResult

def inspect_schema(db_path: str | Path, args: dict, max_sample_rows: int = 5) -> ToolResult:
    try:
        with sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True) as conn:
            objects = conn.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
            requested = args.get("table_name") or args.get("view_name")
            result = {"tables":[], "views":[]}
            for name, kind in objects:
                if requested and name != requested: continue
                cols = conn.execute(f'PRAGMA table_info("{name.replace(chr(34), chr(34)*2)}")').fetchall()
                info = {"name":name, "columns":[{"name":c[1],"type":c[2],"primary_key":bool(c[5])} for c in cols],
                        "foreign_keys":[dict(zip(["id","seq","table","from","to","on_update","on_delete","match"],r)) for r in conn.execute(f'PRAGMA foreign_key_list("{name}")')], "sample_rows":[]}
                if args.get("include_sample_rows"):
                    cur=conn.execute(f'SELECT * FROM "{name}" LIMIT {max(1,min(int(args.get("max_sample_rows",max_sample_rows)),50))}'); info["sample_rows"]=[dict(zip([d[0] for d in cur.description],r)) for r in cur.fetchall()]
                result["tables" if kind=="table" else "views"].append(info)
        return ToolResult(tool_name="sql_schema_inspect",status="success",output=result,preview=f"Inspected {sum(map(len,result.values()))} database objects")
    except Exception as exc:
        return ToolResult(tool_name="sql_schema_inspect",status="error",error=ToolError(error_type=type(exc).__name__,error_message=str(exc),suggested_fix="Check the database path and object name"),preview=str(exc))
