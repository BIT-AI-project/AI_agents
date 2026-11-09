import sqlite3
from pathlib import Path
from autoanalyst.dataset.canonical_views import create_canonical_views

def validate_dataset(db_path: str | Path, refresh_view: bool = False) -> dict[str, object]:
    path = Path(db_path)
    if not path.exists(): raise FileNotFoundError(f"Dataset not found: {path}")
    create_canonical_views(path,replace=refresh_view)
    conn=sqlite3.connect(path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM sales_facts").fetchone()[0]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sales_facts)")]
        required = {"order_date","product_name","product_id","region","quantity","revenue"}
        if not required.issubset(cols) or count == 0: raise ValueError(f"Dataset lacks required concepts: missing={required-set(cols)}, rows={count}")
    finally:
        conn.close()
    return {"path":str(path), "sales_facts_rows":count, "columns":cols}
