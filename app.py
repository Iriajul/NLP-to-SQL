# app.py
import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits import create_sql_agent
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def init_groq():
    """Initialize Groq client"""
    return ChatGroq(
        model_name="llama3-70b-8192",
        groq_api_key=os.getenv("GROQ_API_KEY")
    )

def init_db():
    """Initialize SQL Database connection"""
    return SQLDatabase.from_uri(
        os.getenv("DATABASE_URL"),
        schema="info"
    )

def generate_response(user_query):
    """Process user query and generate response"""
    try:
        # Initialize components
        llm = init_groq()
        db = init_db()
        
        # Create SQL toolkit and get tools
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools = toolkit.get_tools()  # Now actually using this
        
        # Create SQL agent
        agent = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            tools=tools,
            verbose=True
        )
        
        # Process query using the tools
        response = agent.invoke({
            "input": f"Generate SQL query for: {user_query}. Use only the provided tools."
        })
        
        return response['output']
        
    except Exception as e:
        return f"Error: {str(e)}"

# Streamlit UI
st.title("🦙 Groq SQL Query Assistant")
st.write("Ask natural language questions about your database!")

user_input = st.text_input("Enter your question:", 
                         placeholder="e.g., Show top 5 customers by sales")

if st.button("Generate Query"):
    if user_input:
        with st.spinner("Processing..."):
            response = generate_response(user_input)
            
            # Display results
            st.subheader("Generated SQL Query")
            st.code(response, language="sql")
            
            # Add results table if needed
            # result = db.run(response)
            # st.write(result)
    else:
        st.warning("Please enter a question")