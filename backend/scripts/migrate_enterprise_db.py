from sqlalchemy import inspect, text
from app.db import engine, Base
from app import models  # noqa: F401

PRODUCT_COLUMNS = {
    "company": "VARCHAR(160) DEFAULT 'RetailPulse Demo'",
    "brand": "VARCHAR(160) DEFAULT ''",
    "subcategory": "VARCHAR(160) DEFAULT ''",
    "unit_price": "DOUBLE PRECISION DEFAULT 0",
    "unit_cost": "DOUBLE PRECISION DEFAULT 0",
    "currency": "VARCHAR(8) DEFAULT 'INR'",
    "barcode": "VARCHAR(80) DEFAULT ''",
    "supplier": "VARCHAR(160) DEFAULT ''",
}

with engine.begin() as conn:
    Base.metadata.create_all(bind=conn)
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("products")}
    for name, ddl in PRODUCT_COLUMNS.items():
        if name not in cols:
            conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {ddl}"))
    # Enterprise-friendly indexes for common tenant/store/product queries.
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_products_tenant_store_company ON products (tenant_id, store_id, company)",
        "CREATE INDEX IF NOT EXISTS ix_products_tenant_store_brand ON products (tenant_id, store_id, brand)",
        "CREATE INDEX IF NOT EXISTS ix_sales_tenant_store_date ON sales (tenant_id, store_id, sale_date)",
    ]
    for stmt in statements:
        try:
            conn.execute(text(stmt))
        except Exception:
            pass
print("Enterprise database schema is ready.")
