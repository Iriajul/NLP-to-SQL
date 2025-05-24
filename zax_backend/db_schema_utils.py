import psycopg2
from config import DATABASE_URL, DB_SCHEMA

def fetch_schema_text(schema=None):
    """
    Fetches all tables/columns for a Postgres schema and formats as CREATE TABLE statements.
    """
    schema = schema or DB_SCHEMA
    import re
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
        """, (schema,))
        rows = cur.fetchall()
    conn.close()

    # Organize by table
    from collections import defaultdict
    tables = defaultdict(list)
    for table, col, dtype in rows:
        tables[table].append(f"{col} {dtype}")

    schema_strings = []
    for table, columns in tables.items():
        cols = ",\n    ".join(columns)
        schema_strings.append(f"CREATE TABLE {schema}.{table} (\n    {cols}\n);")
    return "\n\n".join(schema_strings)