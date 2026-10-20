-- Sample sales database used by the NLP-to-SQL agent.
-- Column names match zax_backend/table_selector.py.

DROP SCHEMA IF EXISTS info CASCADE;
CREATE SCHEMA info;

CREATE TABLE info.suppliers (
    supplier_id      VARCHAR PRIMARY KEY,          -- e.g. S001
    company_name     VARCHAR NOT NULL,
    contact_person   VARCHAR NOT NULL,
    email            VARCHAR NOT NULL,
    phone            VARCHAR NOT NULL,
    website          VARCHAR NOT NULL,
    country          VARCHAR NOT NULL,
    city             VARCHAR NOT NULL,
    partnership_date DATE NOT NULL,
    payment_terms    VARCHAR NOT NULL,             -- e.g. Net 30
    credit_limit     NUMERIC(12, 2) NOT NULL,
    rating           REAL NOT NULL,                -- 1.0 to 5.0
    status           VARCHAR NOT NULL              -- Active / Inactive / Under Review
);

CREATE TABLE info.products (
    product_id   VARCHAR PRIMARY KEY,              -- e.g. P0001
    product_name VARCHAR NOT NULL,
    category     VARCHAR NOT NULL,
    subcategory  VARCHAR NOT NULL,
    brand        VARCHAR NOT NULL,
    price        NUMERIC(10, 2) NOT NULL,
    stock_level  INTEGER NOT NULL,
    supplier_id  VARCHAR NOT NULL REFERENCES info.suppliers (supplier_id),
    weight_kg    REAL NOT NULL,
    length_cm    REAL NOT NULL,
    width_cm     REAL NOT NULL,
    height_cm    REAL NOT NULL,
    launch_date  DATE NOT NULL
);

CREATE TABLE info.customers (
    customer_id VARCHAR PRIMARY KEY,               -- e.g. C0001
    first_name  VARCHAR NOT NULL,
    last_name   VARCHAR NOT NULL,
    email       VARCHAR NOT NULL,
    city        VARCHAR NOT NULL,
    country     VARCHAR NOT NULL,
    join_date   DATE NOT NULL
);

CREATE TABLE info.sales_representative (
    sales_rep_id    VARCHAR PRIMARY KEY,           -- e.g. SR001
    first_name      VARCHAR NOT NULL,
    last_name       VARCHAR NOT NULL,
    email           VARCHAR NOT NULL,
    phone           VARCHAR NOT NULL,
    region          VARCHAR NOT NULL,
    territory       VARCHAR NOT NULL,
    hire_date       DATE NOT NULL,
    commission_rate REAL NOT NULL,                 -- percent, e.g. 2.7
    annual_target   INTEGER NOT NULL,
    department      VARCHAR NOT NULL,
    status          VARCHAR NOT NULL               -- Active / On Leave / Inactive
);

CREATE TABLE info.orders (
    order_id        VARCHAR PRIMARY KEY,           -- e.g. O00001
    customer_id     VARCHAR NOT NULL REFERENCES info.customers (customer_id),
    sales_rep_id    VARCHAR NOT NULL REFERENCES info.sales_representative (sales_rep_id),
    order_date      DATE NOT NULL,
    total_amount    NUMERIC(12, 2) NOT NULL,       -- sum of line final_amount + tax_amount
    status          VARCHAR NOT NULL,
    payment_method  VARCHAR NOT NULL,
    shipping_method VARCHAR NOT NULL
);

CREATE TABLE info.order_details (
    order_detail_id     VARCHAR PRIMARY KEY,       -- e.g. OD000001
    order_id            VARCHAR NOT NULL REFERENCES info.orders (order_id),
    product_id          VARCHAR NOT NULL REFERENCES info.products (product_id),
    quantity            INTEGER NOT NULL,
    unit_price          NUMERIC(10, 2) NOT NULL,
    subtotal            NUMERIC(12, 2) NOT NULL,   -- quantity * unit_price
    discount_percentage REAL NOT NULL,
    discount_amount     NUMERIC(12, 2) NOT NULL,
    final_amount        NUMERIC(12, 2) NOT NULL,   -- subtotal - discount_amount
    tax_rate            REAL NOT NULL,             -- percent
    tax_amount          NUMERIC(12, 2) NOT NULL
);

CREATE INDEX ON info.products (supplier_id);
CREATE INDEX ON info.orders (customer_id);
CREATE INDEX ON info.orders (sales_rep_id);
CREATE INDEX ON info.orders (order_date);
CREATE INDEX ON info.order_details (order_id);
CREATE INDEX ON info.order_details (product_id);
