#!/usr/bin/env bash
# Create the nlp_to_sql database plus three users, and write their URLs into .env.
#   nlpsql_owner  - owns the tables, used only by seed.py
#   nlpsql_reader - read-only, used to run the AI's SQL (SELECT only, 10s query timeout)
#   nlpsql_app    - reads/writes saved chats (app schema only, no access to the sales data)
# Run once: bash database/create_db.sh   (needs sudo access to the postgres user)
set -euo pipefail
cd "$(dirname "$0")/.."

DB=nlp_to_sql
OWNER_PW=$(openssl rand -hex 16)
READER_PW=$(openssl rand -hex 16)
APP_PW=$(openssl rand -hex 16)

sudo -u postgres psql -v ON_ERROR_STOP=1 -q <<SQL
DROP DATABASE IF EXISTS $DB;
DROP ROLE IF EXISTS nlpsql_reader;
DROP ROLE IF EXISTS nlpsql_app;
DROP ROLE IF EXISTS nlpsql_owner;
CREATE ROLE nlpsql_owner LOGIN PASSWORD '$OWNER_PW';
CREATE ROLE nlpsql_reader LOGIN PASSWORD '$READER_PW';
CREATE ROLE nlpsql_app LOGIN PASSWORD '$APP_PW';
CREATE DATABASE $DB OWNER nlpsql_owner;
SQL

sudo -u postgres psql -v ON_ERROR_STOP=1 -q -d "$DB" <<SQL
REVOKE ALL ON DATABASE $DB FROM PUBLIC;
GRANT CONNECT ON DATABASE $DB TO nlpsql_reader, nlpsql_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER ROLE nlpsql_reader SET default_transaction_read_only = on;
ALTER ROLE nlpsql_reader SET statement_timeout = '10s';
SQL

touch .env
# Replace any old database lines, keep everything else (like GROQ_API_KEY).
sed -i '/^DATABASE_URL=/d;/^DATABASE_ADMIN_URL=/d;/^APP_DATABASE_URL=/d;/^DB_SCHEMA=/d' .env
cat >> .env <<ENV
DATABASE_URL=postgresql://nlpsql_reader:$READER_PW@localhost:5432/$DB
DATABASE_ADMIN_URL=postgresql://nlpsql_owner:$OWNER_PW@localhost:5432/$DB
APP_DATABASE_URL=postgresql://nlpsql_app:$APP_PW@localhost:5432/$DB
DB_SCHEMA=info
ENV
echo "Database $DB created; connection URLs written to .env"
