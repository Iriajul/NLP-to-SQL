"""Ask one question from the command line.

Usage: python -m zax_backend.main "List products with stock level below 50"
"""
import logging
import sys

from .workflow import app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    question = " ".join(sys.argv[1:]) or "List products with stock level below 50"
    result = app.invoke({"user_input": question})
    print("\nSQL:\n" + result["sql"])
    print(f"\nAttempts: {result['attempts']}\n\nAnswer:\n{result['answer']}")
