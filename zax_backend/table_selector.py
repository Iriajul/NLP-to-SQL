import re
from collections import deque

SCHEMA_TABLES = [
    "customers",
    "order_details",
    "orders",
    "products",
    "sales_representative",
    "suppliers"
]

SCHEMA_COLUMNS = [
    "customers.customer_id", "customers.first_name", "customers.last_name", "customers.email", "customers.city", "customers.country", "customers.join_date",
    "order_details.order_detail_id", "order_details.order_id", "order_details.product_id", "order_details.quantity", "order_details.unit_price",
    "order_details.subtotal", "order_details.discount_percentage", "order_details.discount_amount", "order_details.final_amount", "order_details.tax_rate", "order_details.tax_amount",
    "orders.order_id", "orders.customer_id", "orders.sales_rep_id", "orders.order_date", "orders.total_amount", "orders.status", "orders.payment_method", "orders.shipping_method",
    "products.product_id", "products.product_name", "products.category", "products.subcategory", "products.brand", "products.price", "products.stock_level", "products.supplier_id",
    "products.weight_kg", "products.length_cm", "products.width_cm", "products.height_cm", "products.launch_date",
    "sales_representative.sales_rep_id", "sales_representative.first_name", "sales_representative.last_name", "sales_representative.email", "sales_representative.phone", 
    "sales_representative.region", "sales_representative.territory", "sales_representative.hire_date", "sales_representative.commission_rate", "sales_representative.annual_target",
    "sales_representative.department", "sales_representative.status",
    "suppliers.supplier_id", "suppliers.company_name", "suppliers.contact_person", "suppliers.email", "suppliers.phone", "suppliers.website", "suppliers.country", "suppliers.city",
    "suppliers.partnership_date", "suppliers.payment_terms", "suppliers.credit_limit", "suppliers.rating", "suppliers.status"
]

STOPWORDS = {
    "the", "a", "an", "of", "to", "and", "show", "me", "list", "all", "get", "give", "display", "find", "with", "for", "on", "in", "at", "their", "by", "from", "as", "or", "has"
}

# === Relationship graph based on your DDL ===
RELATIONSHIPS = {
    "orders": {"customers": "customer_id", "sales_representative": "sales_rep_id", "order_details": "order_id"},
    "order_details": {"orders": "order_id", "products": "product_id"},
    "products": {"suppliers": "supplier_id", "order_details": "product_id"},
    "suppliers": {"products": "supplier_id"},
    "customers": {"orders": "customer_id"},
    "sales_representative": {"orders": "sales_rep_id"},
}

# === Table Aliases/Nicknames for robust user phrasing ===
TABLE_ALIASES = {
    # sales rep variants
    "sales representative": "sales_representative",
    "sales representatives": "sales_representative",
    "sales rep": "sales_representative",
    "sales reps": "sales_representative",
    "rep": "sales_representative",
    "reps": "sales_representative",
    "representative": "sales_representative",
    "representatives": "sales_representative",
    "salesman": "sales_representative",
    "seller": "sales_representative",
    "sellers": "sales_representative",
    "sales person": "sales_representative",
    # order details/line items
    "order item": "order_details",
    "order items": "order_details",
    "item line": "order_details",
    "item lines": "order_details",
    "line item": "order_details",
    "line items": "order_details",
    # customer
    "client": "customers",
    "clients": "customers",
    # supplier
    "vendor": "suppliers",
    "vendors": "suppliers",
}

def extract_keywords(question):
    print("[DEBUG][extract_keywords] input question:", question)
    words = re.findall(r'\w+', question.lower())
    print("[DEBUG][extract_keywords] words after split:", words)
    filtered = [w for w in words if w not in STOPWORDS]
    print("[DEBUG][extract_keywords] after stopword removal:", filtered)
    return filtered

def singular(word):
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word

def match_tables_and_columns(keywords):
    matched_tables = set()
    matched_columns = set()
    keyword_set = set(keywords)
    keyword_singulars = set(singular(k) for k in keywords)

    def is_id_field(name):
        return name.endswith("_id") or name == "id"

    # === 1. Table matching by direct name, singular/plural, and aliases ===
    for table in SCHEMA_TABLES:
        # Direct match, singular/plural match
        if table in keyword_set or singular(table) in keyword_set or table in keyword_singulars or singular(table) in keyword_singulars:
            matched_tables.add(table)
            for col in SCHEMA_COLUMNS:
                table_name, colname = col.split(".")
                if table_name == table:
                    for k in keyword_set | keyword_singulars:
                        if (k in colname and not is_id_field(colname)) or (k == colname):
                            matched_columns.add(col)
        # Alias/nickname match
        for alias, alias_table in TABLE_ALIASES.items():
            if alias in " ".join(keywords) and alias_table == table:
                matched_tables.add(table)

    # === 2. Multi-entity keyword table matching (boost for multiple mentioned entities) ===
    keyword_all_tables = set()
    for k in keywords + list(keyword_singulars):
        # Check direct, singular, and alias mapping
        for table in SCHEMA_TABLES:
            if k == table or k == singular(table) or k == table.rstrip('s'):
                keyword_all_tables.add(table)
        # Alias mapping
        if k in TABLE_ALIASES:
            keyword_all_tables.add(TABLE_ALIASES[k])
    if len(matched_tables) < len(keyword_all_tables):
        matched_tables.update(keyword_all_tables)

    # === 3. Fallback: If nothing matched, column-only match as before ===
    if not matched_tables:
        for col in SCHEMA_COLUMNS:
            table, colname = col.split(".")
            for k in keyword_set | keyword_singulars:
                if (k in colname and not is_id_field(colname)) or (k == colname):
                    matched_columns.add(col)
                    matched_tables.add(table)

    print("[DEBUG][selector] keywords:", keywords)
    print("[DEBUG][selector] keyword_singulars:", keyword_singulars)
    print("[DEBUG][selector] matched_tables after main pass:", matched_tables)

    # === 4. Heuristic expansion for analytical/transactional language ===
    matched_tables = expand_tables_by_heuristics(matched_tables, keywords)

    # === 5. Dependency-graph expansion as before ===
    matched_tables = expand_tables_by_dependency_graph(matched_tables)

    # === 6. Analytical column boosting ===
    matched_columns = boost_analytical_columns(matched_tables, matched_columns, keywords)

    return list(matched_tables), list(matched_columns)

def expand_tables_by_heuristics(matched_tables, keywords):
    """
    Heuristic rules for multi-table/relationship and analytical queries.
    """
    keywords_joined = " ".join(keywords)
    # Analytical/transactional language: always include orders for amount spent, revenue, etc.
    spending_keywords = {"spent", "amount", "total", "purchase", "order", "revenue", "sales", "buy", "bought"}
    if any(word in (k.lower() for k in keywords) for word in spending_keywords):
        matched_tables.add("orders")
    # If "order details" or line-item analysis, include order_details
    order_details_aliases = {"order_details", "order item", "order items", "line item", "line items", "item line", "item lines"}
    if any(alias in keywords_joined for alias in order_details_aliases):
        matched_tables.add("order_details")
    # If both product and supplier are mentioned, include both tables
    if "supplier" in keywords and "product" in keywords:
        matched_tables.add("suppliers")
        matched_tables.add("products")
    # If both product and order are mentioned, likely needs order_details as bridge
    if "product" in keywords and ("order" in keywords or "ordered" in keywords):
        matched_tables.add("order_details")
    # If customer and order, include both
    if "customer" in keywords and "order" in keywords:
        matched_tables.add("customers")
        matched_tables.add("orders")
    # If sales rep + order, include both
    if ("sales" in keywords or "sales_rep" in keywords or "representative" in keywords) and "order" in keywords:
        matched_tables.add("sales_representative")
        matched_tables.add("orders")
    return matched_tables

def boost_analytical_columns(matched_tables, matched_columns, keywords):
    """
    For questions about spending, revenue, totals, trends, etc., always include relevant amount and date columns in matched_columns.
    """
    analytical_keywords = {"revenue", "sales", "amount", "total", "spent", "purchase", "trend", "growth", "increase", "decrease", "change", "month", "year", "quarter"}
    if any(ak in (k.lower() for k in keywords) for ak in analytical_keywords):
        for table in matched_tables:
            for col in SCHEMA_COLUMNS:
                if col.startswith(table + ".") and (
                    "amount" in col or
                    "total" in col or
                    "subtotal" in col or
                    "final_amount" in col or
                    "order_date" in col or
                    "date" in col
                ):
                    matched_columns.add(col)
        # Also: always add orders.total_amount and order_details.final_amount if orders/order_details in matched_tables
        if "orders" in matched_tables:
            matched_columns.add("orders.total_amount")
            matched_columns.add("orders.order_date")
        if "order_details" in matched_tables:
            matched_columns.add("order_details.final_amount")
    return matched_columns

def expand_tables_by_dependency_graph(matched_tables):
    """
    For every pair of tables in matched_tables, find the shortest join path.
    Add all tables along the path to matched_tables.
    """
    tables = list(matched_tables)
    all_tables_needed = set(matched_tables)
    for i in range(len(tables)):
        for j in range(i+1, len(tables)):
            path = find_join_path(tables[i], tables[j])
            if path:
                all_tables_needed.update(path)
    print("[DEBUG][dependency-graph] tables after join-path expansion:", all_tables_needed)
    return all_tables_needed

def find_join_path(table1, table2):
    """
    Returns list of tables to traverse to get from table1 to table2, excluding table1.
    If already directly connected, returns [table2].
    If not connected, returns [].
    """
    if table1 == table2:
        return []
    visited = set()
    queue = deque([(table1, [])])
    while queue:
        current, path = queue.popleft()
        if current == table2:
            return path
        visited.add(current)
        neighbors = RELATIONSHIPS.get(current, {})
        for neighbor in neighbors:
            if neighbor not in visited:
                queue.append((neighbor, path + [neighbor]))
    return []