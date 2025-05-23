from typing import Annotated, Any, TypedDict
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from tools import list_tables_tool, get_schema_tool, query_to_database
from prompts import query_check_prompt, query_gen_prompt
from config import llm

# State definition
class State(TypedDict):
    messages: Annotated[list[Any], add_messages]

# Error handling
def handle_tool_error(state: State):
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {"messages": [ToolMessage(
        content=f"Error: {repr(error)}\n please fix your mistakes.",
        tool_call_id=tc["id"]
    ) for tc in tool_calls]}

def create_node_from_tool_with_fallback(tools: list) -> RunnableWithFallbacks:
    return ToolNode(tools).with_fallbacks([RunnableLambda(handle_tool_error)], exception_key="error")

# Tool nodes
list_tables = create_node_from_tool_with_fallback([list_tables_tool])
get_schema = create_node_from_tool_with_fallback([get_schema_tool])
query_database = create_node_from_tool_with_fallback([query_to_database])

# Query checking setup
llm_with_tools = llm.bind_tools([query_to_database])
check_generated_query = query_check_prompt | llm_with_tools

# Final answer submission
class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""
    final_answer: str = Field(..., description="TThe formatted query results")

llm_with_final_answer = llm.bind_tools([SubmitFinalAnswer])

# Query generator
query_generator = query_gen_prompt | llm_with_final_answer

# Workflow nodes
def first_tool_call(state: State) -> dict[str, list[AIMessage]]:
    return {"messages": [AIMessage(content="", tool_calls=[{
        "name": "sql_db_list_tables",
        "args": {},
        "id": "tool_abcd123"
    }])]}

def check_the_given_query(state: State):
    return {"messages": [check_generated_query.invoke({"messages": [state["messages"][-1]]})]}

def generation_query(state: State):
    message = query_generator.invoke(state)
    # Debug: print the generated message to inspect it
    print("LLM Output:", message)
    # Only accept function tool calls, not raw text or SQL code
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(ToolMessage(
                    content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Only call SubmitFinalAnswer.",
                    tool_call_id=tc["id"]
                ))
    else:
        tool_messages.append(ToolMessage(
            content="Error: No tool call detected. Please only use SubmitFinalAnswer with the formatted answer.",
            tool_call_id="unknown"
        ))
    return {"messages": [message] + tool_messages}

def should_continue(state: State):
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return END
    elif last_message.content.startswith("Error:"):
        return "query_gen"
    return "correct_query"

def llm_get_schema(state: State):
    response = llm.bind_tools([get_schema_tool]).invoke(state["messages"])
    return {"messages": [response]}

# Create workflow
workflow = StateGraph(State)
workflow.add_node("first_tool_call", first_tool_call)
workflow.add_node("list_tables_tool", list_tables)
workflow.add_node("get_schema_tool", get_schema)
workflow.add_node("model_get_schema", llm_get_schema)
workflow.add_node("query_gen", generation_query)
workflow.add_node("correct_query", check_the_given_query)
workflow.add_node("execute_query", query_database)

workflow.add_edge(START, "first_tool_call")
workflow.add_edge("first_tool_call", "list_tables_tool")
workflow.add_edge("list_tables_tool", "model_get_schema")
workflow.add_edge("model_get_schema", "get_schema_tool")
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_conditional_edges(
    "query_gen",
    should_continue,
    {END: END, "query_gen": "query_gen", "correct_query": "correct_query"}
)
workflow.add_edge("correct_query", "execute_query")
workflow.add_edge("execute_query", "query_gen")

app = workflow.compile()