from workflow import app

if __name__ == "__main__":
    query = {"messages": [("user", "How many sports catagory product are in stock ?")]}
    response = app.invoke(query)
    # Print the final answer
    last_msg = response["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        print(last_msg.tool_calls[0]["args"]["final_answer"])
    else:
        print(last_msg.content)