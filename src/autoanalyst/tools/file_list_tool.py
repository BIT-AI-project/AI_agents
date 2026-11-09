from pathlib import Path
from autoanalyst.state.models import ToolResult

def list_artifacts(run_dir):
    def handler(args):
        paths=[str(p) for p in Path(run_dir).rglob("*") if p.is_file()]
        return ToolResult(tool_name="file_list_artifacts",status="success",output={"files":paths},preview=f"{len(paths)} run artifacts")
    return handler
