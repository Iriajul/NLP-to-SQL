"""Create the info schema and fill it with realistic, consistent sample data.

Usage: python database/seed.py
Needs DATABASE_ADMIN_URL in .env (a user that can create tables).
"""
import os
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from faker import Faker
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SEED = 42
TODAY = date.today()
N_SUPPLIERS, N_PRODUCTS, N_CUSTOMERS, N_REPS, N_ORDERS = 30, 200, 500, 25, 5000
HISTORY_DAYS = 540  # about 18 months of orders

random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

CATALOG = {
    "Electronics": {"Laptops": (600, 2500), "Phones": (200, 1400), "Audio": (30, 400), "Accessories": (10, 120)},
    "Furniture": {"Chairs": (60, 700), "Desks": (150, 1200), "Storage": (40, 500)},
    "Home": {"Kitchen": (15, 300), "Bedding": (25, 250), "Decor": (10, 150)},
    "Clothing": {"Men": (15, 200), "Women": (15, 220), "Kids": (10, 80)},
    "Sports": {"Fitness": (20, 600), "Outdoor": (25, 450)},
    "Beauty": {"Skincare": (8, 120), "Haircare": (6, 90)},
}
BRANDS = ["Nova", "Apex", "Lumen", "Vertex", "Orion", "Summit", "Halo", "Zenith", "Pulse", "Atlas",
          "HomeEssentials", "UrbanFit", "PureGlow", "TechWave", "Oakline"]
REGIONS = {
    "North America": ["Northeast", "Southeast", "Midwest", "West Coast"],
    "Europe": ["UK", "Germany", "France", "Nordics"],
    "Asia Pacific": ["Japan", "South Korea", "Australia", "Singapore"],
    "Latin America": ["Brazil", "Mexico"],
}
COUNTRIES = ["USA", "Canada", "UK", "Germany", "France", "Japan", "Australia", "India", "Brazil", "Spain"]
CATEGORY_TAX = {"Electronics": 8.0, "Furniture": 7.0, "Home": 6.0, "Clothing": 5.0, "Sports": 6.0, "Beauty": 5.0}


def money(x):
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def rand_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def make_suppliers():
    rows = []
    for i in range(1, N_SUPPLIERS + 1):
        company = fake.unique.company()
        domain = "".join(c for c in company.lower() if c.isalnum())[:20]
        rows.append((
            f"S{i:03d}", company, fake.name(), f"contact@{domain}.com", fake.phone_number(),
            f"https://www.{domain}.com", random.choice(COUNTRIES), fake.city(),
            rand_date(date(2015, 1, 1), date(2024, 12, 31)),
            random.choice(["Net 15", "Net 30", "Net 45", "Net 60"]),
            money(random.choice([25000, 50000, 100000, 250000, 500000])),
            round(random.uniform(2.0, 5.0), 1),
            random.choices(["Active", "Inactive", "Under Review"], weights=[80, 10, 10])[0],
        ))
    return rows


def make_products(supplier_ids):
    rows = []
    for i in range(1, N_PRODUCTS + 1):
        category = random.choice(list(CATALOG))
        subcategory = random.choice(list(CATALOG[category]))
        low, high = CATALOG[category][subcategory]
        brand = random.choice(BRANDS)
        # A few products are almost out of stock so "low stock" questions have answers.
        stock = random.randint(0, 49) if random.random() < 0.2 else random.randint(50, 1000)
        rows.append((
            f"P{i:04d}", f"{brand} {subcategory} {fake.word().title()}", category, subcategory, brand,
            money(random.uniform(low, high)), stock, random.choice(supplier_ids),
            round(random.uniform(0.1, 40.0), 2), round(random.uniform(5, 200), 1),
            round(random.uniform(5, 120), 1), round(random.uniform(2, 150), 1),
            rand_date(date(2019, 1, 1), TODAY - timedelta(days=200)),
        ))
    return rows


def make_customers():
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        first, last = fake.first_name(), fake.last_name()
        rows.append((
            f"C{i:04d}", first, last, f"{first.lower()}.{last.lower()}{i}@example.com",
            fake.city(), random.choice(COUNTRIES),
            rand_date(TODAY - timedelta(days=HISTORY_DAYS + 900), TODAY - timedelta(days=30)),
        ))
    return rows


def make_reps():
    rows = []
    for i in range(1, N_REPS + 1):
        first, last = fake.first_name(), fake.last_name()
        region = random.choice(list(REGIONS))
        rows.append((
            f"SR{i:03d}", first, last, f"{first.lower()}.{last.lower()}@company.com", fake.phone_number(),
            region, random.choice(REGIONS[region]),
            rand_date(TODAY - timedelta(days=3000), TODAY - timedelta(days=120)),
            round(random.uniform(1.5, 6.0), 2), random.choice([500000, 750000, 1000000, 1500000, 2000000]),
            random.choice(["Enterprise", "SMB", "Government", "Retail"]),
            random.choices(["Active", "On Leave", "Inactive"], weights=[85, 8, 7])[0],
        ))
    return rows


def make_orders(customers, reps, products):
    """Orders and line items. Totals are computed from the lines so the numbers always add up."""
    # Some products get steadily more popular, so growth/trend questions return results.
    growing = set(random.sample([p[0] for p in products], 12))
    product_weights = [1.0] * len(products)
    start = TODAY - timedelta(days=HISTORY_DAYS)
    orders, lines = [], []
    line_no = 0

    dates = sorted(rand_date(start, TODAY) for _ in range(N_ORDERS))
    for i, order_date in enumerate(dates, start=1):
        order_id = f"O{i:05d}"
        progress = (order_date - start).days / HISTORY_DAYS  # 0 at start, 1 today
        for idx, p in enumerate(products):
            product_weights[idx] = 1.0 + (6.0 * progress if p[0] in growing else 0.0)

        customer = random.choice(customers)
        rep = random.choice(reps)
        total = Decimal("0")
        chosen = random.choices(products, weights=product_weights, k=random.randint(1, 4))
        for p in {p[0]: p for p in chosen}.values():  # no duplicate products per order
            line_no += 1
            qty = random.randint(1, 5)
            unit_price = p[5]
            subtotal = money(qty * unit_price)
            disc_pct = random.choices([0, 5, 10, 15, 20, 25], weights=[50, 15, 15, 10, 7, 3])[0]
            disc_amt = money(subtotal * Decimal(disc_pct) / 100)
            final = subtotal - disc_amt
            tax_rate = CATEGORY_TAX[p[2]]
            tax_amt = money(final * Decimal(str(tax_rate)) / 100)
            total += final + tax_amt
            lines.append((f"OD{line_no:06d}", order_id, p[0], qty, unit_price, subtotal,
                          float(disc_pct), disc_amt, final, tax_rate, tax_amt))

        age = (TODAY - order_date).days
        if age < 3:
            status = random.choice(["Pending", "Processing"])
        elif age < 10:
            status = random.choice(["Processing", "Shipped"])
        else:
            status = random.choices(["Delivered", "Cancelled", "Returned"], weights=[90, 6, 4])[0]
        orders.append((order_id, customer[0], rep[0], order_date, total, status,
                       random.choice(["Credit Card", "PayPal", "Bank Transfer", "Debit Card"]),
                       random.choice(["Standard", "Express", "Overnight", "Pickup"])))
    return orders, lines


def main():
    url = os.getenv("DATABASE_ADMIN_URL")
    if not url:
        raise SystemExit("DATABASE_ADMIN_URL is not set in .env")

    suppliers = make_suppliers()
    products = make_products([s[0] for s in suppliers])
    customers = make_customers()
    reps = make_reps()
    orders, lines = make_orders(customers, reps, products)

    conn = psycopg2.connect(url)
    with conn, conn.cursor() as cur:
        cur.execute((ROOT / "database" / "schema.sql").read_text())
        for table, rows in [("suppliers", suppliers), ("products", products), ("customers", customers),
                            ("sales_representative", reps), ("orders", orders), ("order_details", lines)]:
            execute_values(cur, f"INSERT INTO info.{table} VALUES %s", rows)
            print(f"info.{table}: {len(rows)} rows")
        # The read-only app user needs access to the freshly created schema.
        reader = os.getenv("DATABASE_READER_ROLE", "nlpsql_reader")
        cur.execute(f"GRANT USAGE ON SCHEMA info TO {reader}")
        cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA info TO {reader}")
        # Saved-chats tables; IF NOT EXISTS keeps existing chats when reseeding.
        cur.execute((ROOT / "database" / "app_schema.sql").read_text())
    conn.close()


if __name__ == "__main__":
    main()
