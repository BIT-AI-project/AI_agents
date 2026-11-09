from autoanalyst.tools.sql_query_tool import execute_query
from autoanalyst.tools.sql_schema_tool import inspect_schema
from autoanalyst.dataset.validator import validate_dataset

def test_select_query_and_schema(config,tmp_path):
    validate_dataset(config.dataset_path)
    result=execute_query(config.dataset_path,{"query":"SELECT COUNT(*) AS n FROM sales_facts"},tmp_path)
    assert result.status=="success" and result.output["preview_rows"][0]["n"]>0
    schema=inspect_schema(config.dataset_path,{"view_name":"sales_facts"})
    assert schema.status=="success" and schema.output["views"][0]["name"]=="sales_facts"

def test_mutating_query_rejected(config,tmp_path):
    result=execute_query(config.dataset_path,{"query":"DROP TABLE retail_transactions"},tmp_path)
    assert result.status=="error" and result.error.error_type=="PermissionError"

def test_multi_statement_rejected(config,tmp_path):
    result=execute_query(config.dataset_path,{"query":"SELECT 1; SELECT 2"},tmp_path)
    assert result.status=="error"
