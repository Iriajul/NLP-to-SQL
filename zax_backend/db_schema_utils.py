from collections import defaultdict

from sqlalchemy import text

from .config import DB_SCHEMA, engine

COLUMNS_SQL = text("""
    SELECT table_name, column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = :schema
    ORDER BY table_name, ordinal_position
""")

# pg_constraint is readable by any user, unlike information_schema's key views.
FOREIGN_KEYS_SQL = text("""
    SELECT src.relname, a.attname, dst.relname, b.attname
    FROM pg_constraint c
    JOIN pg_class src ON src.oid = c.conrelid
    JOIN pg_class dst ON dst.oid = c.confrelid
    JOIN pg_namespace n ON n.oid = src.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
    JOIN pg_attribute b ON b.attrelid = c.confrelid AND b.attnum = c.confkey[1]
    WHERE c.contype = 'f' AND n.nspname = :schema
""")


def fetch_schema_text(schema=None, only_tables=None):
    """Return CREATE TABLE text for the schema (optionally only some tables), with join hints."""
    schema = schema or DB_SCHEMA
    with engine.connect() as conn:
        rows = conn.execute(COLUMNS_SQL, {"schema": schema}).all()
        fks = conn.execute(FOREIGN_KEYS_SQL, {"schema": schema}).all()

    tables = defaultdict(list)
    for table, col, dtype in rows:
        tables[table].append(f"{col} {dtype}")

    names = [t for t in (only_tables or tables) if t in tables]
    parts = []
    for table in names:
        cols = ",\n    ".join(tables[table])
        parts.append(f"CREATE TABLE {schema}.{table} (\n    {cols}\n);")

    joins = [f"-- {s}.{sc} -> {d}.{dc}" for s, sc, d, dc in fks if s in names and d in names]
    if joins:
        parts.append("-- Foreign keys (use these for JOINs):\n" + "\n".join(sorted(joins)))
    return "\n\n".join(parts)
