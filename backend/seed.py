"""Development/demo database reset and seed.

WARNING: This script deletes the entire PostgreSQL public schema. Never run it
against a production database containing real customer data.
"""
from datetime import datetime, timedelta
import math, random
from sqlalchemy import text
from app.db import Base, engine, SessionLocal
from app.models import Tenant, Store, User, Product, Sale
from app.auth import hash_password


def reset_database():
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        Base.metadata.create_all(bind=engine)
    else:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)


def main():
    reset_database()
    db=SessionLocal()
    try:
        tenant=Tenant(name="Demo Supermarket Group",slug="demo-supermarket")
        db.add(tenant); db.flush()
        store=Store(tenant_id=tenant.id,name="Bengaluru Branch",location="Bengaluru, Karnataka")
        db.add(store); db.flush()

        users=[
            ("owner@retailpulse.ai","owner123","OWNER"),
            ("manager@retailpulse.ai","manager123","MANAGER"),
            ("staff@retailpulse.ai","staff123","STAFF"),
            ("analyst@retailpulse.ai","analyst123","ANALYST"),
            ("customer@retailpulse.ai","customer123","CUSTOMER"),
        ]
        for email,password,role in users:
            db.add(User(tenant_id=tenant.id,store_id=store.id,email=email,password_hash=hash_password(password),role=role))

        products=[
            ("SKU-RICE","Rice 5kg","Staples",120,7,40,45),
            ("SKU-OIL","Cooking Oil 1L","Staples",90,5,30,32),
            ("SKU-SUGAR","Sugar 1kg","Staples",150,5,35,38),
            ("SKU-MILK","Milk 1L","Dairy",80,2,25,55),
            ("SKU-TEA","Tea 250g","Beverages",110,7,30,28),
            ("SKU-COLA","Soft Drinks","Beverages",100,5,35,40),
            ("SKU-SOAP","Bath Soap","Personal Care",130,8,30,24),
            ("SKU-DETERGENT","Detergent 1kg","Home Care",95,7,30,30),
        ]
        for sku,name,cat,stock,lead,safety,base in products:
            p=Product(
                tenant_id=tenant.id,store_id=store.id,sku=sku,name=name,category=cat,
                company="RetailPulse Demo",brand="Demo Brand",current_stock=stock,
                lead_time_days=lead,safety_stock=safety,unit_price=100,unit_cost=70,currency="INR"
            )
            db.add(p); db.flush()
            for d in range(150):
                date=datetime.utcnow()-timedelta(days=149-d)
                weekly=1+0.15*math.sin(2*math.pi*d/7)
                seasonal=1+0.20*math.sin(2*math.pi*d/60)
                noise=random.uniform(.85,1.15)
                qty=max(0,round(base*weekly*seasonal*noise))
                db.add(Sale(tenant_id=tenant.id,store_id=store.id,product_id=p.id,sale_date=date,quantity=qty))
        db.commit()
    finally:
        db.close()

    print("RetailPulse AI demo database reset and seeded successfully.")
    print("OWNER    owner@retailpulse.ai / owner123")
    print("MANAGER  manager@retailpulse.ai / manager123")
    print("STAFF    staff@retailpulse.ai / staff123")
    print("ANALYST  analyst@retailpulse.ai / analyst123")
    print("CUSTOMER customer@retailpulse.ai / customer123")


if __name__ == "__main__":
    main()
