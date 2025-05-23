import os
import warnings
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq

# Suppress warnings globally
warnings.filterwarnings("ignore")

# Load environment variables
load_dotenv()

# Get configuration from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")
DB_SCHEMA = os.getenv("DB_SCHEMA", "info")

if not DATABASE_URL:
    raise EnvironmentError("DATABASE_URL not set in environment.")

# Database setup
db = SQLDatabase.from_uri(DATABASE_URL, schema=DB_SCHEMA)

# Language model setup
llm = ChatGroq(model="llama3-70b-8192", temperature=0.1)