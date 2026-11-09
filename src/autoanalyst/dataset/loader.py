"""UCI workbook ingestion and SQLite dataset validation."""
import sqlite3
from pathlib import Path
import pandas as pd
from autoanalyst.dataset.canonical_views import create_canonical_views
from autoanalyst.dataset.validator import validate_dataset

SOURCE_COLUMNS={"InvoiceNo":"invoice_no","StockCode":"stock_code","Description":"description","Quantity":"quantity","InvoiceDate":"invoice_date","UnitPrice":"unit_price","CustomerID":"customer_id","Country":"country"}

def build_database(workbook_path: str|Path, database_path: str|Path, sheet_name: str="Online Retail") -> dict[str, object]:
    """Convert the original UCI Excel workbook to SQLite without dropping transaction rows.

    Null descriptions use StockCode in the analytical view; missing customer IDs remain NULL.
    Negative quantities and cancellation invoices are preserved as negative revenue.
    """
    source=Path(workbook_path).resolve(); destination=Path(database_path).resolve()
    if not source.is_file(): raise FileNotFoundError(f"Online Retail workbook not found: {source}")
    destination.parent.mkdir(parents=True,exist_ok=True)
    build_path=destination.with_name(destination.stem+".build"+destination.suffix)
    if build_path.exists(): build_path.unlink()
    frame=pd.read_excel(source,sheet_name=sheet_name,engine="openpyxl")
    missing=set(SOURCE_COLUMNS)-set(frame.columns)
    if missing: raise ValueError(f"UCI workbook missing required columns: {sorted(missing)}")
    frame=frame[list(SOURCE_COLUMNS)].rename(columns=SOURCE_COLUMNS)
    frame["invoice_no"]=frame["invoice_no"].astype("string")
    frame["stock_code"]=frame["stock_code"].astype("string")
    frame["description"]=frame["description"].astype("string")
    frame["country"]=frame["country"].astype("string")
    customer_ids=pd.to_numeric(frame["customer_id"],errors="coerce").astype("Int64")
    frame["customer_id"]=customer_ids.map(lambda value: str(int(value)) if pd.notna(value) else None).astype(object)
    frame["quantity"]=pd.to_numeric(frame["quantity"],errors="raise").astype("int64")
    frame["unit_price"]=pd.to_numeric(frame["unit_price"],errors="raise").astype("float64")
    frame["invoice_date"]=pd.to_datetime(frame["invoice_date"],errors="raise").dt.strftime("%Y-%m-%d %H:%M:%S")
    row_count=len(frame)
    try:
        conn=sqlite3.connect(build_path)
        try:
            frame.to_sql("retail_transactions",conn,if_exists="replace",index=False,chunksize=20_000,
                dtype={"invoice_no":"TEXT","stock_code":"TEXT","description":"TEXT","quantity":"INTEGER","invoice_date":"TEXT","unit_price":"REAL","customer_id":"TEXT","country":"TEXT"})
            conn.execute("CREATE INDEX idx_retail_stock_code ON retail_transactions(stock_code)")
            conn.execute("CREATE INDEX idx_retail_invoice_date ON retail_transactions(invoice_date)")
            conn.execute("CREATE INDEX idx_retail_country ON retail_transactions(country)")
            conn.commit()
        finally: conn.close()
        create_canonical_views(build_path)
        validation=validate_dataset(build_path)
        if validation["sales_facts_rows"]!=row_count: raise ValueError("Canonical view row count differs from the source workbook")
        build_path.replace(destination)
    except Exception:
        if build_path.exists(): build_path.unlink()
        raise
    return validate_dataset(destination)

def load_dataset(path: str|Path) -> dict[str, object]:
    """Ensure a configured SQLite database exposes the canonical sales facts view."""
    return validate_dataset(path)
