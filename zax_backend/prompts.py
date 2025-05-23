from langchain_core.prompts import ChatPromptTemplate

query_check_system = """You are a PostgreSQL expert. Carefully review the PostgreSQL query for common mistakes, including:

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

# UPDATED: Now accepts the schema dynamically for each prompt!
query_gen_system_prompt = """
You are a PostgreSQL expert. Your ONLY job is to generate a single, complete, and syntactically correct PostgreSQL query that answers the input question.

DATABASE SCHEMA:
{schema}

STRICT INSTRUCTIONS:
- Output ONLY the SQL query. DO NOT include explanations, tool calls, function calls (such as SubmitFinalAnswer), code blocks, or any answer or commentary.
- DO NOT output any text, tool call, or answer after the SQL. ONLY the SQL query must be in your response.
- DO NOT call any function or tool, DO NOT output SubmitFinalAnswer, DO NOT output a final answer or summary.
- DO NOT wrap your output in code blocks.
- DO NOT output anything except the SQL.

ADDITIONAL SQL GENERATION GUIDELINES:
- Unless the user requests a specific number of results, add LIMIT 5 to your query.
- Prefer to order results by a relevant column for interesting/meaningful answers.
- Never SELECT *; only select the relevant columns needed to answer the question.
- If you cannot answer with the data available, output a SQL query that will return an empty result set (e.g., add WHERE 1=0), but do NOT make anything up.
- NEVER write DML statements (INSERT, UPDATE, DELETE, DROP, etc.). Only SELECT queries are allowed.

"""

# UPDATED: Accepts {schema} and {user_input} as dynamic variables!
query_gen_prompt = ChatPromptTemplate.from_messages([
    ("system", query_gen_system_prompt),
    ("human", "{user_input}")
])

sql_correction_system_prompt = """
You are a PostgreSQL expert specializing in debugging SQL queries.
Your previous query failed with the following error:

Error:
{db_error}

Your previous SQL:
{sql}

Please fix the query to address the error and ONLY output the corrected SQL.
DO NOT output explanations, error messages, tool calls, or code blocks. ONLY output the corrected SQL query.
"""

sql_correction_prompt = ChatPromptTemplate.from_messages([
    ("system", sql_correction_system_prompt),
    ("placeholder", "{messages}")
])