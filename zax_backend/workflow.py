"""LangGraph pipeline: question -> SQL -> check -> run (fix and retry on error) -> answer.

    START -> rewrite_question -> generate_sql -> check_sql -> execute_sql --ok--> answer -> END
                                                                 ^    |
                                                                 |  error (retries left)
                                                              fix_sql <-+

rewrite_question turns a follow-up ("now only for Germany") into a standalone question
using the earlier turns in `history`. Without history it just passes the question through.
"""
import logging
from typing import TypedDict

import groq
from langgraph.graph import END, START, StateGraph

from .config import get_llm
from .db_schema_utils import fetch_schema_text
from .prompts import answer_prompt, query_check_prompt, query_gen_prompt, rewrite_prompt, sql_correction_prompt
from .table_selector import extract_keywords, match_tables_and_columns
from .tools import clean_sql, run_query

log = logging.getLogger(__name__)

MAX_FIXES = 3
MAX_ROWS_FOR_ANSWER = 50
MAX_HISTORY_TURNS = 3
MAX_ANSWER_CHARS_IN_HISTORY = 600


class Turn(TypedDict):
    question: str
    sql: str
    answer: str


class State(TypedDict, total=False):
    user_input: str         # what the user typed
    history: list[Turn]     # earlier turns of the conversation, oldest first
    question: str           # standalone version of user_input; used by every later step
    schema: str
    tables: list[str]
    sql: str
    columns: list[str]
    rows: list[tuple]
    error: str | None
    attempts: int          # how many times the SQL was run
    sql_history: list[str]  # every SQL tried, for the UI
    answer: str


def _ask(prompt, values, tries=3) -> str:
    for attempt in range(1, tries + 1):
        try:
            return get_llm().invoke(prompt.invoke(values)).content
        except groq.BadRequestError as e:
            # Groq sometimes fails to parse gpt-oss output ("output_parse_failed"); a retry usually works.
            if "output_parse_failed" not in str(e) or attempt == tries:
                raise
            log.warning("Groq output_parse_failed, retrying (%d/%d)", attempt, tries - 1)


def format_history(history: list[Turn]) -> str:
    parts = []
    for i, t in enumerate(history[-MAX_HISTORY_TURNS:], 1):
        answer = t["answer"][:MAX_ANSWER_CHARS_IN_HISTORY]
        parts.append(f"[{i}] User: {t['question']}\nSQL: {t['sql']}\nAnswer: {answer}")
    return "\n\n".join(parts)


def rewrite_question(state: State):
    history = state.get("history") or []
    if not history:
        return {"question": state["user_input"]}
    question = _ask(rewrite_prompt, {"history": format_history(history), "user_input": state["user_input"]})
    question = question.strip().strip('"').strip()
    log.info("rewrote follow-up: %r -> %r", state["user_input"], question)
    return {"question": question or state["user_input"]}


def generate_sql(state: State):
    question = state["question"]
    tables, _ = match_tables_and_columns(extract_keywords(question))
    schema = fetch_schema_text(only_tables=tables or None)
    log.info("selected tables: %s", tables)
    sql = clean_sql(_ask(query_gen_prompt, {"schema": schema, "user_input": question}))
    return {"schema": schema, "tables": tables, "sql": sql, "attempts": 0, "sql_history": []}


def check_sql(state: State):
    sql = clean_sql(_ask(query_check_prompt, {
        "schema": state["schema"], "user_input": state["question"], "sql": state["sql"]}))
    return {"sql": sql or state["sql"]}  # keep the original if the checker returns nothing


def execute_sql(state: State):
    columns, rows, error = run_query(state["sql"])
    log.info("attempt %d: %s -> %s", state["attempts"] + 1, state["sql"], error or f"{len(rows)} rows")
    return {"columns": columns, "rows": rows, "error": error,
            "attempts": state["attempts"] + 1, "sql_history": state["sql_history"] + [state["sql"]]}


def fix_sql(state: State):
    sql = clean_sql(_ask(sql_correction_prompt, {
        "schema": state["schema"], "sql": state["sql"],
        "db_error": state["error"], "user_input": state["question"]}))
    return {"sql": sql}


def answer(state: State):
    if state.get("error"):
        return {"answer": f"Sorry, I couldn't build a working query after {state['attempts']} attempts.\n\n"
                          f"Last error: {state['error']}"}
    result = [state["columns"]] + list(state["rows"][:MAX_ROWS_FOR_ANSWER])
    text = _ask(answer_prompt, {"sql": state["sql"], "result": result, "user_input": state["question"]})
    return {"answer": text}


def after_execute(state: State):
    if state.get("error") and state["attempts"] <= MAX_FIXES:
        return "fix_sql"
    return "answer"


workflow = StateGraph(State)
workflow.add_node("rewrite_question", rewrite_question)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("check_sql", check_sql)
workflow.add_node("execute_sql", execute_sql)
workflow.add_node("fix_sql", fix_sql)
workflow.add_node("answer", answer)

workflow.add_edge(START, "rewrite_question")
workflow.add_edge("rewrite_question", "generate_sql")
workflow.add_edge("generate_sql", "check_sql")
workflow.add_edge("check_sql", "execute_sql")
workflow.add_conditional_edges("execute_sql", after_execute, ["fix_sql", "answer"])
workflow.add_edge("fix_sql", "execute_sql")
workflow.add_edge("answer", END)

app = workflow.compile()
