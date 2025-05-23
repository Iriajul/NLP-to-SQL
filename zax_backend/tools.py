from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_core.tools import tool
from config import db, llm

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