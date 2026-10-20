"""Tests that need the database but no LLM / API key. Run: pytest -q"""
from zax_backend.db_schema_utils import fetch_schema_text
from zax_backend.table_selector import extract_keywords, match_tables_and_columns
from zax_backend.tools import check_read_only, clean_sql, run_query


def tables_for(question):
    tables, _ = match_tables_and_columns(extract_keywords(question))
    return set(tables)


def test_selector_picks_obvious_tables():
    assert tables_for("Show the average rating of suppliers by country") == {"suppliers"}
    assert {"customers", "orders"} <= tables_for("List the top 3 customers by total amount spent")


def test_selector_adds_join_tables():
    # products and orders are only connected through order_details.
    assert {"products", "orders", "order_details"} <= tables_for("Which products were ordered most?")


def test_selector_alias_matches_whole_words_only():
    assert "sales_representative" in tables_for("orders handled by each rep")
    assert "sales_representative" not in tables_for("report the products in stock")


def test_clean_sql_strips_fences_and_semicolon():
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert clean_sql("  SELECT 1;  ") == "SELECT 1"


def test_read_only_guard():
    assert check_read_only("SELECT 1") is None
    assert check_read_only("WITH x AS (SELECT 1) SELECT * FROM x") is None
    assert check_read_only("DELETE FROM info.orders")
    assert check_read_only("SELECT 1; DROP TABLE info.orders")


def test_run_query_returns_rows():
    columns, rows, error = run_query("SELECT count(*) AS n FROM info.orders")
    assert error is None and columns == ["n"] and rows[0][0] > 0


def test_run_query_reports_db_errors():
    _, _, error = run_query("SELECT no_such_column FROM info.orders")
    assert error.startswith("Error:") and "no_such_column" in error


def test_database_user_cannot_write():
    # Gets past the text guard (starts with WITH), but the read-only DB user must still refuse.
    _, _, error = run_query("WITH d AS (DELETE FROM info.orders RETURNING 1) SELECT count(*) FROM d")
    assert error and "read-only" in error


def test_schema_text_includes_join_hints():
    text = fetch_schema_text(only_tables=["orders", "customers"])
    assert "CREATE TABLE info.orders" in text and "CREATE TABLE info.products" not in text
    assert "orders.customer_id -> customers.customer_id" in text
