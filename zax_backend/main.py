from workflow import app

if __name__ == "__main__":
    query = {
        "user_input": "Show me the customers email addresses", 
        "last_query_result": None,
        "last_sql": ""
    }
    print("Initial state:", query)
    response = app.invoke(query)
    print("Response:", response)