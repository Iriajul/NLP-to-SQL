from db_schema_utils import fetch_schema_text
from typing import Annotated, Any, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from tools import list_tables_tool, get_schema_tool, query_to_database
from prompts import query_check_prompt, query_gen_prompt, sql_correction_prompt
from langchain.schema import AIMessage, HumanMessage
from config import llm

# --- Utility to detect if DB result is an error (simple version) ---
def is_db_error(result):
    # You may want to tune this for your actual DB error formats
    return isinstance(result, str) and (result.startswith("Error:") or "error" in result.lower())

# --- The main workflow node for executing SQL with retry/correction ---
def execute_with_correction(state, max_retries=3):
    messages = state.get("messages", [])
    # Use last_sql directly, do not regenerate
    sql_query = state.get("last_sql", "")
    last_sql = sql_query
    db_result = None
    last_error = None
    attempt = 0

    print(f"[INITIAL SQL GENERATED]: {sql_query}")

    while attempt < max_retries:
        if not sql_query:
            print(f"[SQL_QUERY][Attempt {attempt+1} failed]: LLM returned empty SQL!")
            db_result = "Error: LLM returned empty SQL"
            last_error = db_result
            break

        db_result = query_to_database.invoke(sql_query)
        if not is_db_error(db_result):
            print(f"[SQL_QUERY]: {sql_query}")
            print(f"[DB_RESULT]: {db_result}")
            state["last_sql"] = sql_query
            state["last_query_result"] = db_result
            state["messages"] = messages + [
                AIMessage(content=f"[DB_RESULT]\nQuery: {sql_query}\nResult: {db_result}")
            ]
            return state

        last_error = db_result
        attempt += 1
        print(f"[SQL_QUERY][Attempt {attempt} failed]: {sql_query}")
        print(f"[DB_ERROR]: {db_result}")

        # Correction round: ask LLM to fix SQL given the error
        correction_prompt_value = sql_correction_prompt.invoke({
            "sql": sql_query,
            "db_error": db_result,
            "messages": [HumanMessage(content=state.get("user_input", ""))]
        })
        correction_message = correction_prompt_value.to_messages()[-1]
        sql_query = correction_message.content.strip()
        last_sql = sql_query
        print(f"[LLM CORRECTION OUTPUT][Attempt {attempt}]: {sql_query}")

        if not sql_query:
            print("[ERROR] LLM correction returned empty SQL. Stopping retry loop.")
            break

    state["last_sql"] = last_sql
    state["last_query_result"] = last_error
    state["messages"] = messages + [
        AIMessage(content=f"Sorry, the system was unable to generate a working SQL query for your request after {attempt} attempts.\nLast error: {last_error}")
    ]
    return state

# --- State definition ---
class State(TypedDict):
    messages: Annotated[list[Any], add_messages]
    last_query_result: Any
    last_sql: str

# --- Tool wrappers ---
def handle_tool_error(state: State):
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {"messages": [AIMessage(
        content=f"Error: {repr(error)}\n please fix your mistakes.",
        tool_call_id=tc["id"]
    ) for tc in tool_calls]}

def create_node_from_tool_with_fallback(tools: list) -> RunnableWithFallbacks:
    return ToolNode(tools).with_fallbacks([RunnableLambda(handle_tool_error)], exception_key="error")

list_tables = create_node_from_tool_with_fallback([list_tables_tool])
get_schema = create_node_from_tool_with_fallback([get_schema_tool])

llm_with_tools = llm.bind_tools([query_to_database])
check_generated_query = query_check_prompt | llm_with_tools

class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""
    final_answer: str = Field(..., description="The formatted query results")

llm_with_final_answer = llm.bind_tools([SubmitFinalAnswer])
query_generator = query_gen_prompt | llm

# --- Nodes ---
def first_tool_call(state: State) -> dict:
    return {"messages": [AIMessage(content="", tool_calls=[{
        "name": "sql_db_list_tables",
        "args": {},
        "id": "tool_abcd123"
    }])], "last_query_result": None, "last_sql": ""}

def check_the_given_query(state: State):
    last_message = state["messages"][-1]
    sql_to_check = last_message.content  # or adjust extraction if needed
    check_prompt_value = query_check_prompt.invoke({"messages": [HumanMessage(content=sql_to_check)]})
    checked_query = check_prompt_value.to_messages()[-1]
    return {"messages": [checked_query]}

# --- IMPORTANT: Only generate SQL, do NOT allow SubmitFinalAnswer here ---

def generation_query(state: State):
    question = state["messages"][-1].content if state["messages"] else state.get("user_input", "")
    schema_text = fetch_schema_text()
    prompt_input = {
        "schema": schema_text,
        "user_input": question
    }
    # Correct: use the pipeline to get the LLM output
    message = query_generator.invoke(prompt_input)
    sql_text = message.content if hasattr(message, "content") else ""
    return {"messages": [message], "last_sql": sql_text}

def execute_and_store_query(state: State):
    sql_query = state.get("last_sql", "")
    if not sql_query:
        db_result = "Error: No SQL query found."
    else:
        db_result = query_to_database.invoke(sql_query)
    print(f"[SQL_QUERY]: {sql_query}")
    print(f"[DB_RESULT]: {db_result}")
    return {
        "messages": state["messages"] + [
            AIMessage(content=f"[DB_RESULT]\nQuery: {sql_query}\nResult: {db_result}")
        ],
        "last_query_result": db_result,
        "last_sql": sql_query
    }

def submit_answer_from_result(state: State):
    db_result = state.get("last_query_result")
    if not db_result or db_result.startswith("Error"):
        return {"messages": [AIMessage(content="No data found or an error occurred. Unable to answer the question from the database.")]}
    prompt = (
        "You are a database assistant. ONLY use the following data to answer the user's question. "
        "If you cannot answer from the data, say you do not have enough information. "
        f"Database result: {db_result}\nFormat it for the user."
    )
    message = llm_with_final_answer.invoke([HumanMessage(content=prompt)])
    return {"messages": [message]}

def should_continue(state: State):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return END
    elif last_message.content.startswith("Error:") or "No data found" in last_message.content:
        return END
    return "correct_query"

def llm_get_schema(state: State):
    response = llm.bind_tools([get_schema_tool]).invoke(state["messages"])
    return {"messages": [response]}

# --- WORKFLOW ---
workflow = StateGraph(State)
workflow.add_node("first_tool_call", first_tool_call)
workflow.add_node("list_tables_tool", list_tables)
workflow.add_node("get_schema_tool", get_schema)
workflow.add_node("model_get_schema", llm_get_schema)
workflow.add_node("query_gen", generation_query)
workflow.add_node("correct_query", check_the_given_query)
#workflow.add_node("execute_query", execute_and_store_query)
workflow.add_node("execute_query", execute_with_correction)
workflow.add_node("submit_final_answer", submit_answer_from_result)

workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_edge("query_gen", "correct_query")
workflow.add_edge("correct_query", "execute_query")
workflow.add_conditional_edges(
    "query_gen",
    lambda state: "execute_query",  # Always execute SQL, do not allow END or correct_query here!
    {"execute_query": "execute_query"}
)
workflow.add_edge("execute_query", "submit_final_answer")

app = workflow.compile()