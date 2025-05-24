import psycopg2
from config import DATABASE_URL, DB_SCHEMA

def fetch_schema_text(schema=None, only_tables=None):
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

    from collections import defaultdict
    tables = defaultdict(list)
    for table, col, dtype in rows:
        if only_tables is None or table in only_tables:
            tables[table].append(f"{col} {dtype}")

    # --- DEBUG PRINTS ---
    if only_tables:
        print("[DEBUG] fetch_schema_text: Filtering for tables:", only_tables)
        print("[DEBUG] fetch_schema_text: Available tables after filtering:", list(tables.keys()))
    else:
        print("[DEBUG] fetch_schema_text: No filtering, using all tables.")

    schema_strings = []
    if only_tables:
        for table in only_tables:
            if table in tables:
                cols = ",\n    ".join(tables[table])
                schema_strings.append(f"CREATE TABLE {schema}.{table} (\n    {cols}\n);")
    else:
        for table, columns in tables.items():
            cols = ",\n    ".join(columns)
            schema_strings.append(f"CREATE TABLE {schema}.{table} (\n    {cols}\n);")
    return "\n\n".join(schema_strings)