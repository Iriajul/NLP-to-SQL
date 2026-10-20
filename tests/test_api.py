"""API tests with a fake LLM (no API key needed). Chats created here are deleted afterwards."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from api import chats
from api.server import app
from zax_backend import workflow

client = TestClient(app)


def parse_events(body):
    return [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in body.strip().split("\n\n")]


def ask(payload):
    with client.stream("POST", "/api/ask", json=payload) as r:
        assert r.status_code == 200
        return parse_events("".join(r.iter_text()))


@pytest.fixture
def created_chats():
    ids = []
    yield ids
    for chat_id in ids:
        chats.delete_chat(chat_id)


@pytest.fixture
def fake_llm(monkeypatch):
    """Rewrite -> fixed standalone question; SQL -> a count query; answer -> fixed text."""
    seen = []

    def fake(prompt, values):
        seen.append(values)
        if "history" in values:
            return "How many products are in the Electronics category?"
        if "result" in values:
            return "Some products."
        return "SELECT count(*) FROM info.products WHERE category = 'Electronics'"
    monkeypatch.setattr(workflow, "_ask", fake)
    return seen


def test_schema_lists_tables_with_columns():
    data = client.get("/api/schema").json()
    names = {t["name"] for t in data["tables"]}
    assert names == {"customers", "orders", "order_details", "products", "suppliers", "sales_representative"}
    orders = next(t for t in data["tables"] if t["name"] == "orders")
    assert orders["rows"] > 0 and any(c["name"] == "order_date" for c in orders["columns"])


def test_ask_streams_steps_then_json_safe_result(monkeypatch, created_chats):
    replies = {"gen": "SELECT product_id, price, launch_date FROM info.products ORDER BY price DESC LIMIT 2",
               "answer": "Two products."}
    monkeypatch.setattr(workflow, "_ask", lambda p, v: replies["answer"] if "result" in v else replies["gen"])

    events = ask({"question": "two priciest products"})
    created_chats.append(events[-2][1]["id"])

    assert [e for e, _ in events] == ["step"] * 5 + ["chat", "result"]
    assert events[0][1]["node"] == "rewrite_question"
    result = events[-1][1]
    assert result["columns"] == ["product_id", "price", "launch_date"]
    assert isinstance(result["rows"][0][1], float) and len(result["rows"][0][2]) == 10  # Decimal, date -> JSON
    assert result["answer"] == "Two products."


def test_new_chat_is_saved_and_listed(fake_llm, created_chats):
    events = ask({"question": "How many products are there?"})
    chat = events[-2][1]
    created_chats.append(chat["id"])

    assert chat["title"] == "How many products are there?"
    assert chat["id"] in [c["id"] for c in client.get("/api/chats").json()]
    saved = client.get(f"/api/chats/{chat['id']}").json()
    assert [m["question"] for m in saved["messages"]] == ["How many products are there?"]
    assert saved["messages"][0]["result"]["rows"][0][0] > 0


def test_follow_up_in_saved_chat_uses_stored_history(fake_llm, created_chats):
    first = ask({"question": "How many products are there?"})
    chat_id = first[-2][1]["id"]
    created_chats.append(chat_id)

    second = ask({"question": "and in Electronics?", "chat_id": chat_id})

    assert second[-2][1] == {"id": chat_id}  # same chat, no new one created
    assert second[-1][1]["question"] == "How many products are in the Electronics category?"
    rewrite_call = next(v for v in fake_llm if "history" in v)
    assert "How many products are there?" in rewrite_call["history"]  # history came from the database
    saved = client.get(f"/api/chats/{chat_id}").json()
    assert [m["question"] for m in saved["messages"]] == ["How many products are there?", "and in Electronics?"]


def test_new_chat_moves_to_top_after_reply(fake_llm, created_chats):
    a = ask({"question": "first chat"})[-2][1]["id"]
    b = ask({"question": "second chat"})[-2][1]["id"]
    created_chats.extend([a, b])
    ask({"question": "more", "chat_id": a})

    order = [c["id"] for c in client.get("/api/chats").json()]
    assert order.index(a) < order.index(b)


def test_delete_chat(fake_llm):
    chat_id = ask({"question": "temporary"})[-2][1]["id"]
    assert client.delete(f"/api/chats/{chat_id}").status_code == 200
    assert client.get(f"/api/chats/{chat_id}").status_code == 404
    assert client.delete(f"/api/chats/{chat_id}").status_code == 404


def test_unknown_or_invalid_chat_id():
    assert client.post("/api/ask", json={"question": "x", "chat_id": str(uuid.uuid4())}).status_code == 404
    assert client.post("/api/ask", json={"question": "x", "chat_id": "not-a-uuid"}).status_code == 422
    assert client.get("/api/chats/not-a-uuid").status_code == 422


def test_ask_rejects_empty_question():
    assert client.post("/api/ask", json={"question": ""}).status_code == 422


def test_long_question_title_is_shortened():
    title = chats.make_title("word " * 40)
    assert len(title) <= chats.TITLE_LENGTH and title.endswith("…")
