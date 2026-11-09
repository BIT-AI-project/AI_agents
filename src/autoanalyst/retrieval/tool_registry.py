from dataclasses import dataclass
from autoanalyst.tools.base import Tool

@dataclass
class ToolRegistry:
    tools: dict[str,Tool]
    def summaries(self): return [tool.summary() for tool in self.tools.values()]
    def get(self,name): return self.tools.get(name)

def build_registry(db_path,run_dir,config):
    from autoanalyst.tools.sql_schema_tool import inspect_schema
    from autoanalyst.tools.sql_query_tool import execute_query
    from autoanalyst.tools.python_execution_tool import python_tool
    from autoanalyst.tools.report_tool import save_report
    from autoanalyst.tools.file_list_tool import list_artifacts
    definitions=[
      ("sql_schema_inspect","Inspect SQLite schema","Inspect tables, columns, keys and sample rows.","Inspect the read-only business database schema before writing queries.",{"type":"object","properties":{"table_name":{"type":"string"},"view_name":{"type":"string"},"include_sample_rows":{"type":"boolean"},"max_sample_rows":{"type":"integer"}}},["sql","database","schema"],["inspect schema"],["Show sales_facts columns"],"low","schema",lambda a:inspect_schema(db_path,a,config.max_schema_sample_rows)),
      ("sql_query","Read-only SQL query","Run a SELECT or WITH query against SQLite.","Aggregate and filter sales_facts. Mutations are rejected; large results can be saved as CSV.",{"type":"object","properties":{"query":{"type":"string"},"output_file_name":{"type":"string"},"max_rows":{"type":"integer"}},"required":["query"]},["sql","database","sales","comparison","region"],["query sales by region"],["Compare product revenue by quarter"],"low","table",lambda a:execute_query(db_path,a,run_dir/"intermediate",config.max_sql_rows)),
      ("python_execute","Python analysis and chart","Calculate metrics and save PNG charts.","Execute Python in a timed child process with pandas and matplotlib; charts belong in CHART_DIR.",{"type":"object","properties":{"code":{"type":"string"},"description":{"type":"string"},"expected_files":{"type":"array","items":{"type":"string"}}},"required":["code"]},["python","chart","visualization","analysis"],["create chart"],["Plot sales trend"],"medium","analysis",python_tool(run_dir,db_path,config.python_timeout_seconds)),
      ("save_markdown_report","Save Markdown report","Write the final analysis as a Markdown file.","Save final findings, tables, caveats, and relative chart links in the run reports directory.",{"type":"object","properties":{"title":{"type":"string"},"executive_summary":{"type":"string"},"sections":{"type":"array"},"tables":{"type":"array"},"chart_file_paths":{"type":"array"},"assumptions":{"type":"array"},"limitations":{"type":"array"},"status":{"type":"string"}}},["report","markdown"],["save report"],["Write findings and chart links"],"low","markdown",lambda a:save_report(a,run_dir/"reports")),
      ("file_list_artifacts","List run artifacts","List files produced in the current run.","Find report, chart, and intermediate artifact paths.",{"type":"object","properties":{}},["file","artifact"],["list files"],["Find saved charts"],"low","files",list_artifacts(run_dir))]
    return ToolRegistry({d[0]:Tool(name=d[0],title=d[1],description=d[2],long_description=d[3],parameters_json_schema=d[4],tags=d[5],capabilities=d[6],examples=d[7],risk_level=d[8],output_type=d[9],handler=d[10]) for d in definitions})
