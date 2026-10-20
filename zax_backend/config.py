import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sqlalchemy import create_engine

# Load .env from the project root, no matter where the code is run from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
DB_SCHEMA = os.getenv("DB_SCHEMA", "info")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

if not DATABASE_URL:
    raise EnvironmentError("DATABASE_URL not set in .env (run: bash database/create_db.sh)")

# SQLAlchemy 2.1 defaults "postgresql://" to psycopg 3; we use psycopg2.
engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1), pool_pre_ping=True)


def get_llm():
    if not os.getenv("GROQ_API_KEY"):
        raise EnvironmentError("GROQ_API_KEY is empty. Get a key at https://console.groq.com/keys and add it to .env")
    # max_retries lets the client wait and retry when Groq's per-minute rate limit is hit.
    return ChatGroq(model=GROQ_MODEL, temperature=0.0, max_retries=5)
