import sqlite3
from pathlib import Path

SALES_FACTS_SQL = '''CREATE VIEW IF NOT EXISTS sales_facts AS
SELECT invoice_date AS order_date,
       CAST(strftime('%Y', invoice_date) AS INTEGER) AS year,
       CAST((CAST(strftime('%m', invoice_date) AS INTEGER) + 2) / 3 AS INTEGER) AS quarter,
       CAST(strftime('%m', invoice_date) AS INTEGER) AS month,
       COALESCE(NULLIF(TRIM(description), ''), 'StockCode: ' || stock_code) AS product_name,
       stock_code AS product_id,
       NULL AS category_name,
       country AS region,
       quantity,
       ROUND(quantity * unit_price, 2) AS revenue,
       invoice_no,
       stock_code,
       customer_id,
       unit_price,
       CASE WHEN UPPER(invoice_no) LIKE 'C%' THEN 1 ELSE 0 END AS is_cancellation
FROM retail_transactions'''

def create_canonical_views(db_path: str | Path, replace: bool = False) -> None:
    conn=sqlite3.connect(db_path)
    try:
        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='view' AND name='sales_facts'").fetchone()
        if exists and not replace: return
        if exists: conn.execute("DROP VIEW sales_facts")
        conn.execute(SALES_FACTS_SQL.replace("IF NOT EXISTS ", ""))
        conn.commit()
    finally:
        conn.close()
