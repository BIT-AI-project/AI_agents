"""Subprocess Python runner with timeout and per-run environment paths."""
import ast, json, os, subprocess, sys, tempfile, time
from pathlib import Path
from autoanalyst.state.models import ToolError, ToolResult

def _validate_code(code: str) -> None:
    """Reject obvious process/network escape hatches before subprocess execution."""
    tree=ast.parse(code)
    denied_modules={"subprocess","socket","requests","urllib","http","ftplib","telnetlib","ctypes","multiprocessing","shutil","pathlib","tempfile","importlib","sys"}
    denied_calls={"eval","exec","compile","__import__","breakpoint","input"}
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[alias.name.split(".")[0] for alias in node.names] if isinstance(node,ast.Import) else [(node.module or "").split(".")[0]]
            if denied_modules.intersection(names): raise ValueError(f"Import is blocked in analysis code: {sorted(denied_modules.intersection(names))}")
        if isinstance(node,ast.Call):
            if isinstance(node.func,ast.Name) and node.func.id in denied_calls: raise ValueError(f"Call is blocked in analysis code: {node.func.id}")
            if isinstance(node.func,ast.Name) and node.func.id=="open": raise ValueError("Direct file access is blocked; use CHART_DIR for matplotlib output")
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=="os" and node.func.attr in {"system","popen","open","remove","unlink","rename","replace","mkdir","makedirs","rmdir","chmod","chdir","startfile","walk","listdir"}:
                raise ValueError(f"Filesystem/process API is blocked: os.{node.func.attr}")

def run_python(code: str, run_dir: str|Path, db_path: str|Path, timeout: int=60, expected_files: list[str]|None=None) -> ToolResult:
    started=time.perf_counter(); root=Path(run_dir).resolve()
    for name in ("charts","reports","intermediate"): (root/name).mkdir(parents=True,exist_ok=True)
    env={"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT",""),"PYTHONPATH":os.environ.get("PYTHONPATH",""),
         "MPLBACKEND":"Agg","MPLCONFIGDIR":str(root/"intermediate"/"mplconfig"),"DB_PATH":str(Path(db_path).resolve()),"RUN_OUTPUT_DIR":str(root),"CHART_DIR":str(root/"charts"),"REPORT_DIR":str(root/"reports"),"INTERMEDIATE_DIR":str(root/"intermediate"),"HOME":str(root),"USERPROFILE":str(root)}
    Path(env["MPLCONFIGDIR"]).mkdir(parents=True,exist_ok=True)
    # Deliberately do not forward credentials or arbitrary environment variables.
    try:
        _validate_code(code)
        with tempfile.TemporaryDirectory(prefix="aa-python-",dir=root) as tmp:
            script=Path(tmp)/"analysis.py"; script.write_text(code,encoding="utf-8")
            proc=subprocess.run([sys.executable,"-I",str(script)],capture_output=True,text=True,timeout=timeout,env=env,cwd=root)
        created=[]
        for folder in (root/"charts",root/"reports",root/"intermediate"):
            created.extend(str(p) for p in folder.iterdir() if p.is_file())
        for rel in expected_files or []:
            p=(root/rel).resolve()
            if root not in p.parents and p != root: raise ValueError("expected file path escapes run directory")
            if not p.is_file():
                return ToolResult(tool_name="python_execute",status="error",error=ToolError(error_type="MissingExpectedFile",error_message=f"Expected output file was not created: {rel}",suggested_fix="Save the requested artifact under the run output directory"),output={"stdout":proc.stdout,"stderr":proc.stderr,"created_files":created},preview=f"Missing expected file: {rel}")
        result_line=next((line[7:] for line in reversed(proc.stdout.splitlines()) if line.startswith("RESULT:")),None)
        parsed=None
        if result_line:
            try: parsed=json.loads(result_line)
            except json.JSONDecodeError: parsed={"parse_error":"RESULT line was not valid JSON","raw":result_line}
        if proc.returncode:
            return ToolResult(tool_name="python_execute",status="error",output={"stdout":proc.stdout,"stderr":proc.stderr,"traceback":proc.stderr},error=ToolError(error_type="PythonExecutionError",error_message=proc.stderr[-3000:] or f"Exited {proc.returncode}",suggested_fix="Correct the code using the traceback"),preview="Python execution failed",metadata={"execution_time_ms":round((time.perf_counter()-started)*1000,2)})
        charts=[p for p in created if Path(p).parent==root/"charts" and Path(p).suffix.lower()==".png"]
        return ToolResult(tool_name="python_execute",status="success",output={"stdout":proc.stdout,"stderr":proc.stderr,"returned_result":parsed,"created_files":created,"chart_files":charts},artifacts=created,preview=proc.stdout[-1000:],metadata={"execution_time_ms":round((time.perf_counter()-started)*1000,2)})
    except subprocess.TimeoutExpired as exc:
        return ToolResult(tool_name="python_execute",status="error",error=ToolError(error_type="TimeoutError",error_message=f"Python timed out after {timeout}s",suggested_fix="Reduce the computation"),output={"stdout":exc.stdout or "","stderr":exc.stderr or ""},preview="Execution timed out")
    except Exception as exc:
        return ToolResult(tool_name="python_execute",status="error",error=ToolError(error_type=type(exc).__name__,error_message=str(exc),suggested_fix="Check sandbox paths and code"),preview=str(exc))
