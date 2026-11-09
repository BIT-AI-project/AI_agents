from pathlib import Path
from autoanalyst.sandbox.python_runner import run_python
from autoanalyst.tools.report_tool import save_report

def test_python_runner_result_and_error(config,tmp_path):
    ok=run_python("import json\nprint('RESULT:'+json.dumps({'ok':True}))",tmp_path,config.dataset_path,10)
    assert ok.status=="success" and ok.output["returned_result"]["ok"]
    fail=run_python("raise ValueError('test failure')",tmp_path,config.dataset_path,10)
    assert fail.status=="error" and "test failure" in fail.error.error_message

def test_report_file_created(tmp_path):
    result=save_report({"title":"Unit report","executive_summary":"Done","sections":[]},tmp_path)
    assert result.status=="success" and Path(result.output["report_file_path"]).exists()
