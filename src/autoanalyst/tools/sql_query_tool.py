import re, sqlite3, time
from pathlib import Path
import pandas as pd
from autoanalyst.state.models import ToolError, ToolResult

_MUTATION=re.compile(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|DETACH|REPLACE|CREATE|VACUUM|REINDEX|ANALYZE|GRANT|REVOKE)\b",re.I)
def execute_query(db_path: str|Path, args: dict, intermediate_dir: str|Path, max_rows: int=5000) -> ToolResult:
    query=str(args.get("query", "")); started=time.perf_counter()
    try:
        if not query.strip() or not re.match(r"^\s*(SELECT|WITH)\b",query,re.I) or _MUTATION.search(query):
            raise PermissionError("Only read-only SELECT or WITH queries are allowed")
        if ";" in query.rstrip().rstrip(";"):
            raise PermissionError("Multiple SQL statements are not allowed")
        uri=f"file:{Path(db_path).resolve()}?mode=ro"
        with sqlite3.connect(uri,uri=True) as conn:
            conn.execute("PRAGMA query_only=ON")
            frame=pd.read_sql_query(query,conn)
        row_count=len(frame); preview=frame.head(10).to_dict(orient="records"); artifacts=[]; csv_path=None
        if row_count>max_rows or args.get("output_file_name"):
            folder=Path(intermediate_dir).resolve(); folder.mkdir(parents=True,exist_ok=True)
            name=Path(str(args.get("output_file_name") or "query_results.csv")).name
            if not name.lower().endswith(".csv"): name += ".csv"
            destination=folder/name; frame.to_csv(destination,index=False); csv_path=str(destination); artifacts.append(csv_path)
        output={"row_count":row_count,"column_names":list(frame.columns),"preview_rows":preview,"saved_csv_path":csv_path,"query":query}
        return ToolResult(tool_name="sql_query",status="success",output=output,artifacts=artifacts,preview=f"{row_count} rows; columns: {', '.join(frame.columns)}",metadata={"execution_time_ms":round((time.perf_counter()-started)*1000,2)})
    except Exception as exc:
        return ToolResult(tool_name="sql_query",status="error",error=ToolError(error_type=type(exc).__name__,error_message=str(exc),suggested_fix="Inspect sales_facts schema and use a single SELECT/WITH statement",failed_input_summary={"query":query[:300]}),preview=str(exc),metadata={"execution_time_ms":round((time.perf_counter()-started)*1000,2)})
