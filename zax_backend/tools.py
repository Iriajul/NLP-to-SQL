import re

from sqlalchemy import text

from .config import engine

MAX_ROWS = 500


def clean_sql(raw: str) -> str:
    """Pull the SQL out of a model reply (models often wrap it in ``` fences despite instructions)."""
    raw = (raw or "").strip()
    fenced = re.search(r"```(?:sql|postgresql)?\s*(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if fenced:
        raw = fenced.group(1).strip()
    return raw.rstrip(";").strip()


def check_read_only(sql: str):
    """Return an error message if the SQL is not a single SELECT/WITH query, else None.

    This is a first filter only; the real protection is the read-only database user.
    """
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        return "Error: only SELECT queries are allowed."
    if ";" in sql:
        return "Error: only a single SQL statement is allowed."
    return None


def run_query(sql: str):
    """Run a read-only query. Returns (columns, rows, error)."""
    error = check_read_only(sql)
    if error:
        return [], [], error
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [tuple(r) for r in result.fetchmany(MAX_ROWS)]
        return columns, rows, None
    except Exception as e:  # database errors are fed back to the model to fix the query
        message = str(getattr(e, "orig", e)).strip()
        return [], [], f"Error: {message}"
