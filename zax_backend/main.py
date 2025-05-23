from workflow import app

# Example usage
if __name__ == "__main__":
    query = {"messages": [("user", "How many orders are in pending?")]}
    response = app.invoke(query)
    print(response["messages"][-1].tool_calls[0]["args"]["final_answer"])