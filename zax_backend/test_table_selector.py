from table_selector import extract_keywords, match_tables_and_columns

def test_selector():
    questions = [
        " List sales representatives and the number of orders they handled in their first year",
        " Which product category has the highest return on stock investment?",
        "Identify the products that show a consistent month-over-month revenue growth in the last 4 months",
        "Categorize each supplier as Top, Average, or Low performer based on total revenue from their products.",
        "Identify all orders that include both Electronics and Furniture products",
        "Show the average rating of suppliers by country"
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