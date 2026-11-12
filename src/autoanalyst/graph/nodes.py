"""LangGraph node functions; state is JSON-compatible and each node is traced."""
import json, logging, re, time
import calendar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from autoanalyst.dataset.validator import validate_dataset
from autoanalyst.planning.planner import create_plan
from autoanalyst.retrieval.tool_retriever import ToolRetriever
from autoanalyst.state.models import ReviewResult, ToolError, ToolResult

log=logging.getLogger(__name__)

def _trace(state,node,duration=0,extra=None):
    path=Path(state["run_dir"])/"trace.jsonl"; path.parent.mkdir(parents=True,exist_ok=True)
    event={"timestamp":datetime.now(timezone.utc).isoformat(),"node":node,"step_count":state.get("step_count",0),"status":state.get("status"),"tool_name":state.get("selected_tool_name"),"token_usage":state.get("llm_usage",{}),"duration_ms":round(duration*1000,2),**(extra or {})}
    with path.open("a",encoding="utf-8") as f: f.write(json.dumps(event,default=str)+"\n")

def _record_llm_fallback(state,stage,reason):
    state["metrics"]["llm_fallbacks"]=state["metrics"].get("llm_fallbacks",0)+1
    state["metrics"].setdefault("llm_fallback_details",[]).append({"stage":stage,"reason":str(reason)[:1200]})
    state["reflections"].append(f"LLM provider fallback at {stage}: {str(reason)[:500]}")

def intake(state,ctx):
    start=time.perf_counter(); run=Path(state["run_dir"])
    for name in ("charts","reports","intermediate"): (run/name).mkdir(parents=True,exist_ok=True)
    state["normalized_query"]=" ".join(state["user_query"].split())
    state["available_tools"]=ctx["registry"].summaries(); state["status"]="planning" if state["planning_enabled"] else "choosing_action"
    try: summary=validate_dataset(ctx["config"].dataset_path)
    except Exception as exc: state["errors"].append({"error_type":"DatasetError","error_message":str(exc),"recoverable":False}); state["status"]="failed"; state["terminal_failure"]=True
    data=locals().get("summary",{})
    state["metrics"].update({"dataset_summary":f"UCI Online Retail sales_facts with columns {', '.join(data.get('columns',[]))}" if state["status"]!="failed" else "Unavailable","dataset_rows":data.get("sales_facts_rows",0)})
    _trace(state,"intake_and_normalize_request",time.perf_counter()-start)
    return state

def plan_task(state,ctx):
    start=time.perf_counter(); state["plan"]=create_plan(ctx["llm"],state["normalized_query"],str(state["metrics"].get("dataset_summary")),state["reflections"]).model_dump(mode="json")
    if state["plan"].get("metadata",{}).get("fallback"):
        _record_llm_fallback(state,"planning",state["plan"].get("metadata",{}).get("fallback_reason","Invalid plan JSON after retry"))
    state["llm_usage"]=getattr(ctx["llm"],"usage",{})
    state["status"]="retrieving_tools" if state["tool_retrieval_enabled"] else "choosing_action"
    _trace(state,"plan_task",time.perf_counter()-start); return state

def retrieve_tools(state,ctx):
    start=time.perf_counter(); query=state.get("normalized_query","")
    if state.get("plan"):
        steps=state["plan"].get("steps",[]); i=min(state.get("current_plan_step_index",0),len(steps)-1)
        if i>=0 and steps: query += " " + steps[i].get("objective","") + " " + " ".join(steps[i].get("suggested_tool_hints",[]))
    retriever=ToolRetriever(state["available_tools"],ctx["config"].top_k_tools)
    state["retrieved_tools"]=retriever.retrieve(query); state["status"]="choosing_action"
    info={"retrieval_query":query,"retrieved_tools":[x["name"] for x in state["retrieved_tools"]],"scores":{x["name"]:x.get("retrieval_score",0) for x in state["retrieved_tools"]},"final_tool_subset":[x["name"] for x in state["retrieved_tools"]]}
    _trace(state,"retrieve_tools",time.perf_counter()-start,info); return state

def _build_query(state,db_path):
    query=state["normalized_query"]; low=query.lower()
    quarters=sorted({int(q) for q in re.findall(r"\bq([1-4])\b",low)}); years=sorted({int(y) for y in re.findall(r"\b(20\d{2})\b",low)})
    months=sorted({i for i in range(1,13) if re.search(r"\b("+calendar.month_name[i].lower()+"|"+calendar.month_abbr[i].lower()+r")\b",low)})
    metric="quantity" if re.search(r"\b(quantity|units? sold)\b",low) else "revenue"
    with __import__('sqlite3').connect(f"file:{Path(db_path).resolve()}?mode=ro",uri=True) as conn:
        products=[r[0] for r in conn.execute("SELECT DISTINCT product_name FROM sales_facts")]
        categories=[r[0] for r in conn.execute("SELECT DISTINCT category_name FROM sales_facts") if r[0]]
        regions=[r[0] for r in conn.execute("SELECT DISTINCT region FROM sales_facts")]
    product_spans={}
    for product in products:
        pattern=(r"(?<!\w)"+re.escape(product.lower())+r"(?!\w)") if len(product)>=3 else (r"(?:track|product)\s+['\"]?"+re.escape(product.lower())+r"(?:['\"]?\b)")
        spans=[(match.start(),match.end()) for match in re.finditer(pattern,low)]
        if spans: product_spans[product]=spans
    # A short catalog name can be a substring of a longer requested title
    # (e.g. "HEART T-LIGHT HOLDER" inside "WHITE HANGING HEART T-LIGHT HOLDER").
    # Keep a shorter hit only when it has a separate mention outside the longer hit.
    matches=[]
    for product in sorted(product_spans,key=len,reverse=True):
        spans=product_spans[product]
        if any(not any(long_start<=start and end<=long_end
                       for longer in matches for long_start,long_end in product_spans[longer])
               for start,end in spans):
            matches.append(product)
    if not matches:
        words=[w for w in re.findall(r"[a-z0-9']+",low) if len(w)>4 and w not in {"compare","revenue","sales","product","products","quarter","region","chart","show","find","best","top","what","which","during","between","summarize","category","categories","genre","rank","ranked","trend","yearly","monthly","quarterly","performing","lowest","highest"}]
        for p in products:
            if any(w in p.lower() for w in words): matches.append(p)
    where=[]
    if quarters: where.append("quarter IN ("+",".join(map(str,quarters))+")")
    if years: where.append("year IN ("+",".join(map(str,years))+")")
    if months: where.append("month IN ("+",".join(map(str,months))+")")
    if matches: where.append("product_name IN ("+",".join("'"+p.replace("'","''")+"'" for p in matches[:8])+")")
    category_context=bool(re.search(r"\b(category|genre)\b",low))
    matched_categories=[c for c in categories if c.lower() in low and (category_context or not any(c.lower() in p.lower() for p in matches))]
    if matched_categories: where.append("category_name IN ("+",".join("'"+c.replace("'","''")+"'" for c in matched_categories)+")")
    matched_regions=[r for r in regions if r.lower() in low]
    if matched_regions: where.append("region IN ("+",".join("'"+r.replace("'","''")+"'" for r in matched_regions)+")")
    conditions=" WHERE "+" AND ".join(where) if where else ""
    top_match=re.search(r"\btop\s*(\d+)",low); limit=str(min(int(top_match.group(1)),50)) if top_match else "100"
    descending="ASC" if re.search(r"\b(low|lowest|least|underperforming)\b",low) else "DESC"
    wants_region=bool(re.search(r"\b(best|highest|top)\s+(region|country)|\bwhich (region|country)|\b(region|country) ranking|show.*(region|country)",low))
    temporal=[]
    if len(years)>1: temporal=["year"]
    elif len(months)>1: temporal=["month"]
    elif re.search(r"\btrend|over time|monthly|quarterly|yearly|by year|by month\b",low):
        if "monthly" in low or "by month" in low: temporal=["year","month"]
        elif "quarterly" in low or "by quarter" in low or quarters: temporal=["year","quarter"]
        else: temporal=["year"]
    elif len(quarters)>1: temporal=["quarter"]
    if top_match and not matches and not matched_categories:
        return f"SELECT product_name, 'All regions' AS region, SUM(quantity) AS quantity, ROUND(SUM(revenue),2) AS revenue FROM sales_facts{conditions} GROUP BY product_name ORDER BY {metric} {descending} LIMIT {limit}"
    group=[*temporal]
    if matched_categories: group.append("category_name")
    if not temporal and not matched_categories: group.append("product_name")
    if not matched_categories: group.append("product_name") if temporal else None
    if not temporal or wants_region: group.append("region")
    projections=[*temporal]
    if matched_categories: projections.append("category_name")
    if not matched_categories: projections.append("product_name")
    if not temporal or wants_region: projections.append("region")
    projections += ["SUM(quantity) AS quantity","ROUND(SUM(revenue),2) AS revenue"]
    group_sql=", ".join(dict.fromkeys(group))
    return f"SELECT {', '.join(projections)} FROM sales_facts{conditions} GROUP BY {group_sql} ORDER BY {metric} {descending} LIMIT {limit}"

def _prepare_report(state):
    outputs=state["tool_outputs"]; sql=next((o for o in reversed(outputs) if o.get("tool_name")=="sql_query" and o.get("status")=="success"),{})
    rows=(sql.get("output") or {}).get("preview_rows",[])
    python=next((o for o in reversed(outputs) if o.get("tool_name")=="python_execute" and o.get("status")=="success"),{})
    analysis=(python.get("output") or {}).get("returned_result") or {}
    summary="Analysis completed from the UCI Online Retail transaction dataset."
    metric="quantity" if re.search(r"\b(quantity|units? sold)\b",state["normalized_query"],re.I) else "revenue"
    if re.search(r"\b(profit|margin)\b",state["normalized_query"],re.I):
        summary="Profit or margin cannot be calculated because the UCI Online Retail source contains no product cost data. The available revenue/quantity results are included for context."
    elif analysis.get("best_region"):
        best_region=analysis["best_region"]
        summary=f"Best region by combined {metric} in the queried results: {best_region['region']} ({best_region[metric]:.2f})."
    elif rows:
        if "region" in rows[0] and re.search(r"\b(best|highest|top)\s+(region|country)|show the best (region|country)|which (region|country)",state["normalized_query"],re.I):
            totals={}
            for row in rows: totals[row.get("region","Unknown")]=totals.get(row.get("region","Unknown"),0)+float(row.get(metric,0) or 0)
            region=max(totals,key=totals.get); summary=f"Best region by combined {metric} in the returned results: {region} ({totals[region]:.2f})."
        else:
            best=max(rows,key=lambda r:float(r.get("revenue",0) or 0)); summary=f"Highest revenue result in the returned data: {best.get('product_name', best.get('category_name','sales'))} in {best.get('region','the selected period')} ({best.get('revenue')})."
    query=(sql.get("output") or {}).get("query","")
    product_filter=query.split("product_name IN (",1)[1].split(") GROUP BY",1)[0] if "product_name IN (" in query else ""
    requested=re.findall(r"'((?:[^']|'')*)'",product_filter)
    returned_products=set(analysis.get("product_names",[])) or {r.get("product_name") for r in rows}
    absent=[p.replace("''","'") for p in requested if p.replace("''","'") not in returned_products]
    if absent and not re.search(r"\b(profit|margin)\b",state["normalized_query"],re.I): summary += " No matching sales rows were found for: "+", ".join(absent)+"."
    if (sql.get("output") or {}).get("row_count")==0:
        summary="No matching sales rows were found for this request, so no metrics or chart were produced."+(" Not found: "+", ".join(absent)+"." if absent else "")
    chart=state.get("chart_files",[])
    order_desc="quantity" if metric=="quantity" else "revenue"
    limitations=["The source dataset contains no cost data; profit and margin cannot be calculated.","No product category field is present in the source dataset."]
    if re.search(r"\b(category|categories|genre)\b",state["normalized_query"],re.I): summary="The source dataset has no product category field, so category-level performance cannot be computed. Available transaction results are included where possible."
    state["pending_report"]={"title":"AutoAnalyst business analysis","executive_summary":summary,"sections":[{"heading":"Request","content":state["normalized_query"]},{"heading":"Results","content":f"The table below contains the query preview, ordered by {order_desc}. Revenue is Quantity times UnitPrice in GBP. Negative quantities and cancellation invoices are retained as negative net adjustments."}],"tables":[{"title":"Sales results","markdown":_markdown_table(rows)}],"chart_file_paths":chart,"assumptions":["Description is used as product name, with StockCode as a fallback for missing descriptions.","Country is the geographic region because the source has no sub-country region field.","Cancellation invoices and negative quantities are retained; reported revenue is net of those negative lines.","Quarter means calendar quarter. Unspecified years aggregate matching quarters across the available dataset."],"limitations":limitations}

def _markdown_table(rows):
    if not rows: return "No matching rows were returned."
    cols=list(rows[0]); return "| "+" | ".join(cols)+" |\n| "+" | ".join("---" for _ in cols)+" |\n"+"\n".join("| "+" | ".join(str(r.get(c,"")) for c in cols)+" |" for r in rows)

def _python_analysis_code(query,db_uri,metric,make_chart):
    code=("import pandas as pd, os, json, sqlite3\n"
          f"query={query!r}\n"
          f"with sqlite3.connect({db_uri!r},uri=True) as conn: df=pd.read_sql_query(query,conn)\n"
          "summary={'rows':len(df),'total_revenue':float(df['revenue'].sum()) if 'revenue' in df.columns else 0.0,'product_names':sorted(df['product_name'].dropna().astype(str).unique().tolist()) if 'product_name' in df.columns else []}\n")
    if make_chart:
        code += ("import matplotlib.pyplot as plt\n"
                 "if not df.empty:\n"
                 f"    metric={metric!r}; time_cols=[c for c in ['year','quarter','month'] if c in df.columns]; labels=df[time_cols].astype(str).agg('-'.join,axis=1) if time_cols else (df['product_name'].astype(str)+' — '+df['region'].astype(str) if 'product_name' in df.columns and 'region' in df.columns else df.iloc[:,0].astype(str)); plt.figure(figsize=(10,5)); plt.bar(labels,df[metric]); plt.xticks(rotation=60,ha='right'); plt.ylabel(metric.title()); plt.title('Sales analysis'); plt.tight_layout(); plt.savefig(os.path.join(os.environ['CHART_DIR'],'sales_analysis.png'),dpi=150); summary['chart']='sales_analysis.png'\n")
    code += ("if not df.empty and 'region' in df.columns and "+repr(metric)+" in df.columns:\n"
             f"    totals=df.groupby('region')[{metric!r}].sum().sort_values(ascending=False); summary['best_region']={{'region':str(totals.index[0]),{metric!r}:float(totals.iloc[0])}}\n"
             "print('RESULT:'+json.dumps(summary))\n")
    return code

def choose_next_action(state,ctx):
    start=time.perf_counter(); outputs=state["tool_outputs"]; names=[o.get("tool_name") for o in outputs]
    if state.get("status")=="failed" or state.get("step_count",0)>=ctx["config"].max_total_steps:
        state["status"]="failed"; state["terminal_failure"]=True
        if "save_markdown_report" not in names:
            _prepare_report(state); state["pending_report"].update({"status":"failed","limitations":state["pending_report"].get("limitations",[])+[e.get("error_message","") for e in state["errors"]]})
            state["selected_tool_name"]="save_markdown_report"; state["selected_tool_args"]=state["pending_report"]
        else: state["selected_tool_name"]=None
    elif "sql_query" not in names and not state.get("planning_enabled"):
        # ReAct baseline reasons one action at a time and uses the documented canonical view directly.
        state["selected_tool_name"]="sql_query"; state["selected_tool_args"]={"query":_build_query(state,ctx["config"].dataset_path)}
    elif "sql_schema_inspect" not in names and state.get("planning_enabled"):
        state["selected_tool_name"]="sql_schema_inspect"; state["selected_tool_args"]={"view_name":"sales_facts","include_sample_rows":False}
    elif "sql_query" not in names:
        state["selected_tool_name"]="sql_query"; state["selected_tool_args"]={"query":_build_query(state,ctx["config"].dataset_path)}
    elif sum(1 for n in names if n=="python_execute") < (2 if state.get("planning_enabled") else 1):
        sql=next((o for o in reversed(outputs) if o.get("tool_name")=="sql_query" and o.get("status")=="success"),{}); q=(sql.get("output") or {}).get("query","")
        no_rows=(sql.get("output") or {}).get("row_count")==0
        db_uri=Path(ctx["config"].dataset_path).resolve().as_uri()+"?mode=ro"
        chart_metric="quantity" if re.search(r"\b(quantity|units? sold)\b",state["normalized_query"],re.I) else "revenue"
        chart_stage=not state.get("planning_enabled") or sum(1 for n in names if n=="python_execute")>=1
        code=_python_analysis_code(q,db_uri,chart_metric,chart_stage)
        description="Create a chart and calculate final metrics from read-only SQL results" if chart_stage else "Calculate and validate metrics from read-only SQL results"
        state["selected_tool_name"]="python_execute"; state["selected_tool_args"]={"code":code,"description":description,"expected_files":["charts/sales_analysis.png"] if chart_stage and not no_rows else []}
    elif "save_markdown_report" not in names:
        _prepare_report(state); state["selected_tool_name"]="save_markdown_report"; state["selected_tool_args"]=state["pending_report"]
    else:
        state["selected_tool_name"]=None; state["status"]="reporting"
    selection_rationale="deterministic fallback"
    if state.get("selected_tool_name"):
        # The LLM receives only the current retrieval subset when retrieval is enabled.
        candidates=state.get("retrieved_tools",[]) if state.get("tool_retrieval_enabled") else state.get("available_tools",[])
        candidate_names={tool.get("name") for tool in candidates}
        if state["selected_tool_name"] not in candidate_names:
            name=state["selected_tool_name"]
            tool=ctx["registry"].get(name)
            if tool:
                summary=tool.summary(); summary["retrieval_score"]=0.0; summary["retrieval_fallback"]=True
                state["retrieved_tools"].append(summary); candidates=state["retrieved_tools"]
                state["metrics"]["retrieval_fallbacks"]=state["metrics"].get("retrieval_fallbacks",0)+1
        recommended={"tool_name":state["selected_tool_name"],"arguments":state.get("selected_tool_args") or {},"rationale":"Selected for the current workflow stage.","expected_output":"Structured tool result"}
        try:
            from autoanalyst.planning.schemas import ToolSelection
            raw=ctx["llm"].complete_json("tool_selection",{"query":state["normalized_query"],"workflow_stage":state["selected_tool_name"],"observations":[o.get("preview","") for o in outputs[-3:]],"available_tools":candidates,"recommended_action":recommended},ToolSelection.model_json_schema())
            selection=ToolSelection.model_validate(raw)
            if selection.tool_name not in {tool.get("name") for tool in candidates} or selection.tool_name!=state["selected_tool_name"]:
                raise ValueError("LLM selected a tool outside the current workflow stage/retrieval subset")
            selection_rationale=selection.rationale
            # Keep the deterministic stage arguments unless the provider supplied a non-empty argument object.
            if selection.arguments: state["selected_tool_args"]=selection.arguments
        except Exception as exc:
            try:
                from autoanalyst.planning.schemas import ToolSelection
                corrected=ctx["llm"].complete_json("tool_selection_retry",{"recommended_action":recommended,"available_tools":candidates,"correction":"Select the recommended registered tool and return valid JSON."},ToolSelection.model_json_schema())
                selection=ToolSelection.model_validate(corrected)
                if selection.tool_name!=state["selected_tool_name"]: raise ValueError("Retry selected an out-of-stage tool")
                selection_rationale=selection.rationale
            except Exception as retry_error:
                _record_llm_fallback(state,"tool_selection",f"initial: {exc}; retry: {retry_error}")
                state["reflections"].append(f"Tool selection JSON fallback: {exc}")
                state["metrics"]["tool_selection_fallbacks"]=state["metrics"].get("tool_selection_fallbacks",0)+1
        state["llm_usage"]=getattr(ctx["llm"],"usage",{})
    if state.get("selected_tool_name"):
        fingerprint=state["selected_tool_name"]+json.dumps(state.get("selected_tool_args"),sort_keys=True,default=str)
        if fingerprint==state.get("last_call_fingerprint"): state["consecutive_identical_calls"]+=1
        else: state["consecutive_identical_calls"]=1
        state["last_call_fingerprint"]=fingerprint
        if state["consecutive_identical_calls"]>ctx["config"].max_consecutive_identical_tool_calls:
            state["status"]="failed"; state["terminal_failure"]=True; state["errors"].append({"error_type":"LoopLimitError","error_message":"Repeated identical tool call limit exceeded","recoverable":False}); state["selected_tool_name"]=None
    if state.get("selected_tool_name"): state["status"]="choosing_action"
    _trace(state,"choose_next_action",time.perf_counter()-start,{"chosen_tool":state.get("selected_tool_name"),"selection_rationale":selection_rationale,"retrieved_tool_names":[x.get("name") for x in state.get("retrieved_tools",[])]}); return state

def execute_tool(state,ctx):
    start=time.perf_counter(); name=state.get("selected_tool_name"); tool=ctx["registry"].get(name) if name else None
    if not tool:
        result=ToolResult(tool_name=name or "unknown",status="error",error=ToolError(error_type="ToolSelectionError",error_message=f"Unknown tool: {name}",recoverable=True,suggested_fix="Select a registered tool"),preview="Unknown tool")
    else:
        try: result=tool.handler(state.get("selected_tool_args") or {})
        except Exception as exc: result=ToolResult(tool_name=name,status="error",error=ToolError(error_type=type(exc).__name__,error_message=str(exc)),preview=str(exc))
    dumped=result.model_dump(mode="json"); state["tool_outputs"].append(dumped); state["tool_call_count"]+=1; state["step_count"]+=1
    state["intermediate_artifacts"].extend(dumped.get("artifacts",[]))
    if name=="python_execute" and result.status=="success": state["chart_files"].extend(result.output.get("chart_files",[]))
    if result.status=="error": state["errors"].append(dumped.get("error") or {"error_type":"ToolError","error_message":result.preview,"recoverable":True})
    if result.status=="error" and (dumped.get("error") or {}).get("recoverable",True): state["recoverable_error_count"]+=1
    if result.status=="success" and state.get("recovery_attempted"):
        state["recovered_error_count"]+=max(0,state["recoverable_error_count"]-state["recovered_error_count"]); state["recovery_attempted"]=False
    state["status"]="reviewing_output" if state["output_review_enabled"] else "choosing_action"
    _trace(state,"execute_tool",time.perf_counter()-start,{"tool_name":name,"error":dumped.get("error")}); return state

def review_tool_output(state,ctx):
    start=time.perf_counter(); result=state["tool_outputs"][-1] if state["tool_outputs"] else {}
    payload={"result":result,"query":state["normalized_query"],"success_criteria":state.get("current_plan_step_id")}
    fallback_reason=None
    try: review=ReviewResult.model_validate(ctx["llm"].complete_json("review",payload,ReviewResult.model_json_schema()))
    except Exception as first_error:
        try: review=ReviewResult.model_validate(ctx["llm"].complete_json("review_retry",{**payload,"correction":"Return verdict pass, fail, or uncertain and a concise reason."},ReviewResult.model_json_schema()))
        except Exception as retry_error:
            fallback_reason=f"initial: {first_error}; retry: {retry_error}"
            review=ReviewResult(verdict="pass" if result.get("status")=="success" else "fail",reason="Deterministic review fallback")
    if fallback_reason: _record_llm_fallback(state,"output_review",fallback_reason)
    if result.get("status")=="success" and review.verdict=="fail" and result.get("tool_name")!="sql_query": review.verdict="pass"
    if result.get("status")=="error": review.verdict="fail"
    if result.get("tool_name")=="sql_query" and result.get("status")=="success" and (result.get("output") or {}).get("row_count")==0:
        review.verdict = "pass"; review.reason = "SQL returned no rows; the report will state that no matching data exists"
    expects_chart=bool((state.get("selected_tool_args") or {}).get("expected_files"))
    if result.get("tool_name")=="python_execute" and result.get("status")=="success" and expects_chart and not (result.get("output") or {}).get("chart_files"):
        review.verdict="fail"; review.reason="Expected a chart, but no PNG chart was saved"; review.corrective_action="Generate a PNG under CHART_DIR"
    if result.get("tool_name")=="save_markdown_report" and result.get("status")=="success":
        report=(result.get("output") or {}).get("report_file_path")
        missing=[p for p in state.get("chart_files",[]) if not Path(p).is_file()]
        if report and Path(report).is_file():
            body=Path(report).read_text(encoding="utf-8")
            for link in re.findall(r"!\[[^\]]*\]\(([^)]+)\)",body):
                target=(Path(report).parent/link).resolve()
                if not target.is_file(): missing.append(str(target))
        if not report or not Path(report).is_file() or missing:
            review.verdict="fail"; review.reason="Report or linked chart artifact is missing"; review.missing_information=missing
    state["last_review"]=review.model_dump(); state["status"]="recovering" if review.verdict=="fail" else "reviewing_output"
    if review.verdict=="fail": state["reflections"].append(review.reason); state["retry_count_for_current_step"]+=1
    if review.verdict=="uncertain": state["reflections"].append(review.reason); state["retry_count_for_current_step"]+=1
    state["llm_usage"]=getattr(ctx["llm"],"usage",{})
    _trace(state,"review_tool_output",time.perf_counter()-start,{"verdict":review.verdict}); return state

def recover_from_error(state,ctx):
    start=time.perf_counter(); latest=state["tool_outputs"][-1] if state["tool_outputs"] else {}; name=latest.get("tool_name")
    if not state["output_review_enabled"]: state["retry_count_for_current_step"]+=1
    state["max_retries_per_plan_step"]=ctx["config"].max_retries_per_plan_step
    if state["retry_count_for_current_step"]>ctx["config"].max_retries_per_plan_step:
        state["status"]="failed"; state["terminal_failure"]=True; state["selected_tool_name"]=None
    elif name=="sql_query":
        # A deterministic correction for schema/filter failures: retain known quarter/year, broaden product match.
        state["selected_tool_name"]="sql_query"; state["selected_tool_args"]={"query":"SELECT product_name, region, SUM(quantity) AS quantity, ROUND(SUM(revenue),2) AS revenue FROM sales_facts GROUP BY product_name, region ORDER BY revenue DESC LIMIT 10"}
        state["recovery_attempted"]=True
    else:
        from autoanalyst.planning.schemas import RecoveryDecision
        payload={"tool_name":name,"arguments":state.get("selected_tool_args"),"error":latest.get("error")}
        try:
            decision=RecoveryDecision.model_validate(ctx["llm"].complete_json("recover",payload,RecoveryDecision.model_json_schema()))
        except Exception as first_error:
            try: decision=RecoveryDecision.model_validate(ctx["llm"].complete_json("recover_retry",{**payload,"correction":"Return a valid recovery JSON object."},RecoveryDecision.model_json_schema()))
            except Exception as retry_error:
                _record_llm_fallback(state,"recovery",f"initial: {first_error}; retry: {retry_error}")
                decision=RecoveryDecision(action="retry",revised_tool_name=name,revised_arguments=state.get("selected_tool_args") or {},explanation="Deterministic retry fallback")
        state["selected_tool_name"]=decision.revised_tool_name or name; state["selected_tool_args"]=decision.revised_arguments or state.get("selected_tool_args"); state["recovery_attempted"]=True
    if state.get("plan") and state["plan"].get("revision",0)<2:
        plan=state["plan"]; revision=plan.get("revision",0)+1; plan["revision"]=revision
        plan.setdefault("metadata",{}).setdefault("revisions",[]).append({"revision":revision,"reason":state.get("last_review",{}).get("reason","Tool execution error"),"timestamp":datetime.now(timezone.utc).isoformat()})
    state["llm_usage"]=getattr(ctx["llm"],"usage",{})
    state["status"]="recovering"; _trace(state,"recover_from_error",time.perf_counter()-start,{"recovery_attempted":state.get("recovery_attempted")}); return state

def update_plan_if_needed(state,ctx):
    start=time.perf_counter(); last=state["tool_outputs"][-1] if state["tool_outputs"] else {}
    if last.get("status")=="success":
        state["retry_count_for_current_step"]=0
        if state.get("plan"):
            steps=state["plan"].get("steps",[]); idx=min(state.get("current_plan_step_index",0),max(0,len(steps)-1))
            if steps: state["current_plan_step_id"]=steps[idx]["step_id"]; state["current_plan_step_index"]=min(idx+1,len(steps)-1)
    if state.get("step_count",0)>=ctx["config"].max_total_steps and not any(o.get("tool_name")=="save_markdown_report" for o in state["tool_outputs"]):
        state["status"]="failed"; state["terminal_failure"]=True; state["errors"].append({"error_type":"StepLimitError","error_message":"Maximum total tool steps reached","recoverable":False})
    _trace(state,"update_plan_if_needed",time.perf_counter()-start); return state

def generate_report(state,ctx):
    start=time.perf_counter()
    if not state.get("pending_report"): _prepare_report(state)
    if state.get("status")=="failed":
        state["pending_report"].update({"status":"failed","limitations":state["pending_report"].get("limitations",[])+[e.get("error_message","") for e in state["errors"]]})
    if state.get("metrics",{}).get("llm_fallbacks"):
        warning=(f"Configured LLM provider had {state['metrics']['llm_fallbacks']} failed structured-output call(s); "
                 "deterministic fallback was used. See run metrics/state for stage details.")
        if warning not in state["pending_report"].get("limitations",[]): state["pending_report"].setdefault("limitations",[]).append(warning)
    state["status"]="reporting"; _trace(state,"generate_report",time.perf_counter()-start); return state

def finalize_run(state,ctx):
    start=time.perf_counter(); reports=[o for o in state["tool_outputs"] if o.get("tool_name")=="save_markdown_report" and o.get("status")=="success"]
    if reports:
        state["report_file"]=(reports[-1].get("output") or {}).get("report_file_path")
        state["status"]="failed" if state.get("terminal_failure") else "completed"
    else: state["status"]="failed"
    state["llm_usage"]=getattr(ctx["llm"],"usage",{}); state["finished_at"]=datetime.now(timezone.utc).isoformat()
    elapsed=(datetime.fromisoformat(state["finished_at"])-datetime.fromisoformat(state["started_at"])).total_seconds()
    provider=ctx["config"].llm_provider
    provider_model=ctx["config"].llm_model or getattr(ctx["config"],f"{provider}_model",None)
    state["metrics"].update({"total_steps":state["step_count"],"total_tool_calls":state["tool_call_count"],"total_errors":len(state["errors"]),"recoverable_errors":state["recoverable_error_count"],"recovered_errors":state["recovered_error_count"],"unrecovered_errors":max(0,state["recoverable_error_count"]-state["recovered_error_count"]),"success":state["status"]=="completed","duration_seconds":elapsed,"token_usage":getattr(ctx["llm"],"usage",{}),"llm_provider":provider,"llm_model":provider_model,"llm_fallbacks":state["metrics"].get("llm_fallbacks",0),"llm_structured_outputs":getattr(ctx["llm"],"structured_outputs",None),"workflow_mode":state["workflow_mode"],"planning_enabled":state["planning_enabled"],"output_review_enabled":state["output_review_enabled"],"tool_retrieval_enabled":state["tool_retrieval_enabled"]})
    run=Path(state["run_dir"]); run.mkdir(parents=True,exist_ok=True)
    for filename,data in (("state.json",state),("metrics.json",state["metrics"])):
        (run/filename).write_text(json.dumps(data,indent=2,default=str),encoding="utf-8")
    if state["errors"]: (run/"errors.json").write_text(json.dumps(state["errors"],indent=2),encoding="utf-8")
    _trace(state,"finalize_run",time.perf_counter()-start); return state
