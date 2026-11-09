import sqlite3
from autoanalyst.dataset.validator import validate_dataset
from autoanalyst.graph.nodes import _build_query

def test_online_retail_rows_and_source_semantics(config):
    summary=validate_dataset(config.dataset_path)
    assert summary["sales_facts_rows"]==541909
    with sqlite3.connect(config.dataset_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM retail_transactions WHERE customer_id IS NULL").fetchone()[0]>0
        assert conn.execute("SELECT COUNT(*) FROM retail_transactions WHERE description IS NULL").fetchone()[0]>0
        assert conn.execute("SELECT COUNT(*) FROM sales_facts WHERE quantity<0").fetchone()[0]>0
        assert conn.execute("SELECT COUNT(*) FROM sales_facts WHERE is_cancellation=1").fetchone()[0]>0
        assert conn.execute("SELECT COUNT(*) FROM sales_facts WHERE category_name IS NOT NULL").fetchone()[0]==0

def test_long_exact_product_name_does_not_match_nested_shorter_product(config):
    query="Compare Q3 sales of WHITE HANGING HEART T-LIGHT HOLDER and WHITE METAL LANTERN, and show the best country."
    sql=_build_query({"normalized_query":query},config.dataset_path)
    assert "'HEART T-LIGHT HOLDER'" not in sql
    assert "'WHITE HANGING HEART T-LIGHT HOLDER'" in sql
    assert "'WHITE METAL LANTERN'" in sql
