from table_selector import extract_keywords, match_tables_and_columns

def test_selector():
    questions = [
        "Show all customer emails",
        "List the supplier ratings",
        "Get sales representative phone numbers",
        "Show me the orders with discounts",
        "Products and their categories"
    ]
    for q in questions:
        keywords = extract_keywords(q)
        tables, columns = match_tables_and_columns(keywords)
        print(f"Question: {q}")
        print(f"  Keywords: {keywords}")
        print(f"  Matched Tables: {tables}")
        print(f"  Matched Columns: {columns}\n")

if __name__ == "__main__":
    test_selector()