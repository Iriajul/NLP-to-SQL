"""Runs the full LangGraph pipeline against the real database with a fake LLM (no API key needed)."""
from zax_backend import prompts, workflow


def fake_llm(replies):
    """Replace workflow._ask: return the next scripted reply for each prompt type."""
    calls = []

    def _ask(prompt, values):
        name = {id(prompts.query_gen_prompt): "gen", id(prompts.query_check_prompt): "check",
                id(prompts.sql_correction_prompt): "fix", id(prompts.answer_prompt): "answer",
                id(prompts.rewrite_prompt): "rewrite"}[id(prompt)]
        calls.append((name, values))
        return replies[name].pop(0)
    return _ask, calls


def test_failed_query_is_fixed_and_retried(monkeypatch):
    ask, calls = fake_llm({
        "gen": ["```sql\nSELECT bad_column FROM info.products\n```"],
        "check": ["SELECT bad_column FROM info.products"],
        "fix": ["SELECT count(*) FROM info.products WHERE stock_level < 50"],
        "answer": ["There are some low-stock products."],
    })
    monkeypatch.setattr(workflow, "_ask", ask)

    result = workflow.app.invoke({"user_input": "How many products have stock below 50?"})

    assert result["attempts"] == 2 and result["error"] is None
    assert result["rows"][0][0] > 0
    assert [c[0] for c in calls] == ["gen", "check", "fix", "answer"]
    fix_values = dict(calls)["fix"]
    assert "bad_column" in fix_values["db_error"]  # the real DB error is passed to the fixer


def test_gives_up_after_max_fixes(monkeypatch):
    bad = "SELECT nope FROM info.products"
    ask, calls = fake_llm({"gen": [bad], "check": [bad], "fix": [bad] * 10, "answer": []})
    monkeypatch.setattr(workflow, "_ask", ask)

    result = workflow.app.invoke({"user_input": "anything"})

    assert result["attempts"] == workflow.MAX_FIXES + 1
    assert result["answer"].startswith("Sorry")


HISTORY = [{"question": "Who are the top 3 customers by total amount spent?",
            "sql": "SELECT customer_id, SUM(total_amount) FROM info.orders GROUP BY 1 ORDER BY 2 DESC LIMIT 3",
            "answer": "C0169, C0070 and C0488."}]


def test_first_question_is_not_rewritten(monkeypatch):
    ask, calls = fake_llm({"gen": ["SELECT 1"], "check": ["SELECT 1"], "answer": ["1"]})
    monkeypatch.setattr(workflow, "_ask", ask)

    result = workflow.app.invoke({"user_input": "Count something"})

    assert "rewrite" not in [c[0] for c in calls]  # no extra LLM call without history
    assert result["question"] == "Count something"


def test_follow_up_is_rewritten_and_used_everywhere(monkeypatch):
    standalone = "Who are the top 3 customers in Germany by total amount spent?"
    ask, calls = fake_llm({
        "rewrite": [f'"{standalone}"'],  # quotes from the model are stripped
        "gen": ["SELECT 1"], "check": ["SELECT 1"], "answer": ["done"],
    })
    monkeypatch.setattr(workflow, "_ask", ask)

    result = workflow.app.invoke({"user_input": "now only for Germany", "history": HISTORY})

    assert result["question"] == standalone
    by_step = dict(calls)
    assert "now only for Germany" in by_step["rewrite"]["user_input"]
    assert "top 3 customers" in by_step["rewrite"]["history"] and "SUM(total_amount)" in by_step["rewrite"]["history"]
    for step in ("gen", "check", "answer"):  # later steps see the standalone question, not the fragment
        assert by_step[step]["user_input"] == standalone


def test_history_is_trimmed_to_recent_turns():
    turns = [{"question": f"q{i}", "sql": "SELECT 1", "answer": "x" * 5000} for i in range(6)]
    text = workflow.format_history(turns)
    assert "q0" not in text and "q5" in text
    assert len(text) < workflow.MAX_HISTORY_TURNS * (workflow.MAX_ANSWER_CHARS_IN_HISTORY + 100)


def test_groq_parse_failure_is_retried(monkeypatch):
    import groq
    import httpx

    class FlakyLLM:
        calls = 0

        def invoke(self, _):
            FlakyLLM.calls += 1
            if FlakyLLM.calls == 1:
                raise groq.BadRequestError("output_parse_failed", response=httpx.Response(
                    400, request=httpx.Request("POST", "https://x")), body=None)
            return type("Msg", (), {"content": "ok"})()

    monkeypatch.setattr(workflow, "get_llm", lambda: FlakyLLM())
    assert workflow._ask(prompts.answer_prompt, {"sql": "", "result": "", "user_input": "q"}) == "ok"
    assert FlakyLLM.calls == 2
