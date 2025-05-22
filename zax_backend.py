# zax_backend.py
import os
import warnings
from dotenv import load_dotenv
from typing import Annotated, Literal, Any, TypedDict
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, Field
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import add_messages
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langgraph.prebuilt import ToolNode
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate

# Suppress warnings
warnings.filterwarnings("ignore")

# Database setup
load_dotenv()
db = SQLDatabase.from_uri(
    os.getenv("DATABASE_URL"),
    schema="info"
)

# Language model setup
llm = ChatGroq(model="llama3-70b-8192", temperature=0.10)

# SQL Toolkit setup
toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()

# Get specific tools
list_tables_tool = next((tool for tool in tools if tool.name == "sql_db_list_tables"), None)
get_schema_tool = next((tool for tool in tools if tool.name == "sql_db_schema"), None)

# Custom tool definition
@tool
def query_to_database(query: str) -> str:
    """Execute a PostgreSQL query against the database and return the result."""
    result = db.run_no_throw(query)
    return result if result else "Error: Query failed. Please rewrite your query and try again."

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
query_check_system = """You are a PostgreSQL expert. Carefully review the SQL query for common mistakes, including:

- Issues with NULL handling (e.g., NOT IN with NULLs)
- Improper use of UNION instead of UNION ALL
- Incorrect use of BETWEEN for exclusive ranges
- Data type mismatches or incorrect casting
- Quoting identifiers improperly
- Incorrect number of arguments in functions
- Errors in JOIN conditions

If you find any mistakes, rewrite the query to fix them. If it's correct, reproduce it as is."""

query_check_prompt = ChatPromptTemplate.from_messages([
    ("system", query_check_system),
    ("placeholder", "{messages}")
])
llm_with_tools = llm.bind_tools([query_to_database])
check_generated_query = query_check_prompt | llm_with_tools

# Final answer submission
class SubmitFinalAnswer(BaseModel):
    """Submit the final answer to the user based on the query results."""
    final_answer: str = Field(..., description="TThe formatted query results")

llm_with_final_answer = llm.bind_tools([SubmitFinalAnswer])

# Query generation setup
query_gen_system_prompt = """You are a PostgreSQL expert with a strong attention to detail.Given an input question, output a syntactically correct SQLite query to run, then look at the results of the query and return the answer.

1. DO NOT call any tool besides SubmitFinalAnswer to submit the final answer.

When generating the query:

2. Output the SQL query that answers the input question without a tool call.

3. Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.

4. You can order the results by a relevant column to return the most interesting examples in the database.

5. Never query for all the columns from a specific table, only ask for the relevant columns given the question.

6. If you get an error while executing a query, rewrite the query and try again.

7. If you get an empty result set, you should try to rewrite the query to get a non-empty result set.

8. NEVER make stuff up if you don't have enough information to answer the query... just say you don't have enough information.

9. If you have enough information to answer the input question, simply invoke the appropriate tool to submit the final answer to the user.

10. DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database. Do not return any sql query except answer. """

query_gen_prompt = ChatPromptTemplate.from_messages([
    ("system", query_gen_system_prompt),
    ("placeholder", "{messages}")
])
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
    tool_messages = []
    if message.tool_calls:
        for tc in message.tool_calls:
            if tc["name"] != "SubmitFinalAnswer":
                tool_messages.append(ToolMessage(
                    content=f"Error: The wrong tool was called: {tc['name']}. Please fix your mistakes. Remember to only call SubmitFinalAnswer to submit the final answer. Generated queries should be outputted WITHOUT a tool call.",
                    tool_call_id=tc["id"]
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

# Example usage
if __name__ == "__main__":
    query = {"messages": [("user", "Which product haves the highest price?")]}
    response = app.invoke(query)
    print(response["messages"][-1].tool_calls[0]["args"]["final_answer"])