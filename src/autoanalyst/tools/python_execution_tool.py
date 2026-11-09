from autoanalyst.sandbox.python_runner import run_python

def python_tool(run_dir, db_path, timeout=60):
    def handler(args): return run_python(args.get("code",""),run_dir,db_path,timeout,args.get("expected_files"))
    return handler
