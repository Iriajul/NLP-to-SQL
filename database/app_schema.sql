-- Saved conversations for the web UI. Kept in its own schema so reseeding the sample
-- data (info schema) never deletes chats. Safe to run repeatedly.
-- Only nlpsql_app can read/write here; the AI's read-only user has no access.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.chats (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.messages (
    id         BIGSERIAL PRIMARY KEY,
    chat_id    UUID NOT NULL REFERENCES app.chats (id) ON DELETE CASCADE,
    question   TEXT NOT NULL,   -- what the user typed
    result     JSONB NOT NULL,  -- full API result: standalone question, answer, sql, rows, ...
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS messages_chat_id_idx ON app.messages (chat_id, id);
CREATE INDEX IF NOT EXISTS chats_updated_at_idx ON app.chats (updated_at DESC);

GRANT USAGE ON SCHEMA app TO nlpsql_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO nlpsql_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO nlpsql_app;
