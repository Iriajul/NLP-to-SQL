"""HTTP API for the Next.js frontend.

Run: .venv/bin/uvicorn api.server:app --port 8100 --reload
"""
import json
import logging
import os
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from zax_backend.config import DB_SCHEMA, GROQ_MODEL, engine
from zax_backend.workflow import app as graph

from . import chats

log = logging.getLogger(__name__)
app = FastAPI(title="NLP to SQL API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("WEB_ORIGINS", "http://localhost:3100").split(","),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    chat_id: UUID | None = None  # continue this saved chat; omit to start a new one


def to_json_value(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.get("/api/health")
def health():
    return {"ok": True, "model": GROQ_MODEL, "has_api_key": bool(os.getenv("GROQ_API_KEY"))}


@app.get("/api/schema")
def schema():
    """Tables with their columns and row counts, for the sidebar."""
    with engine.connect() as conn:
        cols = conn.execute(text("""
            SELECT table_name, column_name, data_type FROM information_schema.columns
            WHERE table_schema = :s ORDER BY table_name, ordinal_position"""), {"s": DB_SCHEMA}).all()
        names = sorted({c[0] for c in cols})
        # Exact counts; the tables are small. Names come from information_schema, quoted for safety.
        counts = {t: conn.execute(text(f'SELECT count(*) FROM "{DB_SCHEMA}"."{t}"')).scalar() for t in names}
    tables = {}
    for table, col, dtype in cols:
        tables.setdefault(table, {"name": table, "rows": counts.get(table, 0), "columns": []})
        tables[table]["columns"].append({"name": col, "type": dtype})
    return {"schema": DB_SCHEMA, "tables": list(tables.values())}


@app.get("/api/chats")
def list_chats():
    return chats.list_chats()


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: UUID):
    chat = chats.get_chat(str(chat_id))
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: UUID):
    if not chats.delete_chat(str(chat_id)):
        raise HTTPException(404, "Chat not found")
    return {"ok": True}


@app.post("/api/ask")
def ask(body: Question):
    """Streams pipeline progress as server-sent events: `step` per node, then `chat` and `result` (or `error`).

    The finished turn is saved. Without chat_id a new chat is created (only once an answer exists,
    so failed first questions don't leave empty chats). With chat_id, its recent turns are the
    history used for follow-up questions.
    """
    chat_id = str(body.chat_id) if body.chat_id else None
    if chat_id and not chats.chat_exists(chat_id):
        raise HTTPException(404, "Chat not found")
    history = chats.recent_history(chat_id) if chat_id else []

    def events():
        question = body.question.strip()
        state = {"user_input": question, "history": history}
        try:
            for update in graph.stream(state, stream_mode="updates"):
                for node, values in update.items():
                    state.update(values)
                    yield sse("step", {"node": node, "attempt": state.get("attempts", 0),
                                       "error": values.get("error") if node == "execute_sql" else None})
            result = {
                "question": state.get("question", ""),
                "answer": state.get("answer", ""),
                "sql": state.get("sql", ""),
                "sql_history": state.get("sql_history", []),
                "attempts": state.get("attempts", 0),
                "tables": state.get("tables", []),
                "columns": state.get("columns", []),
                "rows": [[to_json_value(v) for v in row] for row in state.get("rows", [])],
                "error": state.get("error"),
            }
            try:
                chat = {"id": chat_id} if chat_id else chats.create_chat(question)
                chats.add_message(chat["id"], question, result)
                yield sse("chat", chat)
            except Exception:  # still show the answer if saving fails
                log.exception("could not save chat turn")
            yield sse("result", result)
        except Exception as e:  # e.g. Groq rate limit or network error
            yield sse("error", {"message": f"{type(e).__name__}: {e}"})

    # Sync generator: FastAPI runs it in a thread, so the blocking LLM calls don't stall the server.
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
