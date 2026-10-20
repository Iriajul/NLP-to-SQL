"""Saved conversations, stored in the app schema through the nlpsql_app user."""
import json
import os

from sqlalchemy import create_engine, text

import zax_backend.config  # noqa: F401  (loads .env)
from zax_backend.workflow import MAX_HISTORY_TURNS

APP_DATABASE_URL = os.getenv("APP_DATABASE_URL")
if not APP_DATABASE_URL:
    raise EnvironmentError("APP_DATABASE_URL not set in .env (see database/create_db.sh)")

engine = create_engine(APP_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1), pool_pre_ping=True)

TITLE_LENGTH = 60


def make_title(question: str) -> str:
    q = " ".join(question.split())
    return q if len(q) <= TITLE_LENGTH else q[: TITLE_LENGTH - 1].rstrip() + "…"


def create_chat(first_question: str) -> dict:
    with engine.begin() as conn:
        row = conn.execute(text("INSERT INTO app.chats (title) VALUES (:t) RETURNING id, title, updated_at"),
                           {"t": make_title(first_question)}).one()
    return {"id": str(row.id), "title": row.title, "updated_at": row.updated_at.isoformat()}


def chat_exists(chat_id: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1 FROM app.chats WHERE id = CAST(:id AS uuid)"), {"id": chat_id}).first() is not None


def list_chats(limit: int = 100) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, title, updated_at FROM app.chats ORDER BY updated_at DESC LIMIT :n"),
                            {"n": limit}).all()
    return [{"id": str(r.id), "title": r.title, "updated_at": r.updated_at.isoformat()} for r in rows]


def get_chat(chat_id: str) -> dict | None:
    with engine.connect() as conn:
        chat = conn.execute(text("SELECT id, title, updated_at FROM app.chats WHERE id = CAST(:id AS uuid)"),
                            {"id": chat_id}).first()
        if not chat:
            return None
        msgs = conn.execute(text("SELECT question, result FROM app.messages WHERE chat_id = CAST(:id AS uuid) ORDER BY id"),
                            {"id": chat_id}).all()
    return {"id": str(chat.id), "title": chat.title, "updated_at": chat.updated_at.isoformat(),
            "messages": [{"question": m.question, "result": m.result} for m in msgs]}


def delete_chat(chat_id: str) -> bool:
    with engine.begin() as conn:
        return conn.execute(text("DELETE FROM app.chats WHERE id = CAST(:id AS uuid)"), {"id": chat_id}).rowcount > 0


def add_message(chat_id: str, question: str, result: dict):
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO app.messages (chat_id, question, result) VALUES (CAST(:id AS uuid), :q, CAST(:r AS jsonb))"),
                     {"id": chat_id, "q": question, "r": json.dumps(result, default=str)})
        conn.execute(text("UPDATE app.chats SET updated_at = now() WHERE id = CAST(:id AS uuid)"), {"id": chat_id})


def recent_history(chat_id: str) -> list[dict]:
    """Last few successful turns, oldest first, in the shape the workflow expects."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT result FROM app.messages
            WHERE chat_id = CAST(:id AS uuid) AND result->>'error' IS NULL
            ORDER BY id DESC LIMIT :n"""), {"id": chat_id, "n": MAX_HISTORY_TURNS}).all()
    return [{"question": r.result["question"], "sql": r.result["sql"], "answer": r.result["answer"]}
            for r in reversed(rows)]
