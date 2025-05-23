from workflow import app

if __name__ == "__main__":
    # You can replace this string with any question you want to ask your LLM-to-SQL workflow!
    query = {
        "user_input": "How many sports category products are in stock?",  # <-- Change this to any NL question
        "messages": [],
        "last_query_result": None,
        "last_sql": ""
    }
    print("Initial state:", query)
    response = app.invoke(query)
    print("Response:", response)