from workflow import app

if __name__ == "__main__":
    query = {
        "user_input": " List products with stock level below 50 ", 
        "last_query_result": None,
        "last_sql": ""
    }
    response = app.invoke(query)
    # Print only the final formatted answer message!
    print(response["messages"][-1].content)