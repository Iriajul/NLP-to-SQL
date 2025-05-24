import re

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
    "the", "a", "an", "of", "to", "and", "show", "me", "list", "all", "get", "give", "display", "find", "with", "for", "on", "in", "at", "their"
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

    # Only match a table if its name or its singular is in the original keywords/singulars
    for table in SCHEMA_TABLES:
        if table in keyword_set or singular(table) in keyword_set or table in keyword_singulars or singular(table) in keyword_singulars:
            for col in SCHEMA_COLUMNS:
                table_name, colname = col.split(".")
                if table_name == table:
                    for k in keyword_set | keyword_singulars:
                        if (k in colname and not is_id_field(colname)) or (k == colname):
                            matched_columns.add(col)
            if any(col.startswith(table + ".") for col in matched_columns):
                matched_tables.add(table)

    # Fallback: If no tables matched, allow column-only match as before
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

    return list(matched_tables), list(matched_columns)