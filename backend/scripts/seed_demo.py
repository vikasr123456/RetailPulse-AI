from datetime import datetime, timedelta
import math, random
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.db import Base, engine, SessionLocal
from app.models import Tenant, Store, User, Product, Sale
from app.auth import hash_password

random.seed(42)

def get_or_create(db, model, **kwargs):
    obj=db.query(model).filter_by(**kwargs).first()
    if obj:return obj
    obj=model(**kwargs);db.add(obj);db.flush();return obj

def main():
    Base.metadata.create_all(bind=engine)
    db=SessionLocal()
    try:
        tenant=get_or_create(db,Tenant,slug='demo-retail',name='Demo Retail India')
        store=get_or_create(db,Store,tenant_id=tenant.id,name='Bengaluru Main Store',location='Bengaluru')
        owner=db.query(User).filter(User.email=='owner@retailpulse.ai').first()
        if not owner:
            owner=User(tenant_id=tenant.id,store_id=store.id,email='owner@retailpulse.ai',password_hash=hash_password('owner123'),role='OWNER',is_active=True)
            db.add(owner);db.flush()

        catalog=[
            ('SKU-RICE-001','Premium Rice 5kg','Groceries',42,7,20),
            ('SKU-OIL-001','Sunflower Oil 1L','Groceries',18,10,12),
            ('SKU-MILK-001','Toned Milk 1L','Dairy',8,2,15),
            ('SKU-BIS-001','Biscuits Family Pack','Snacks',75,5,25),
            ('SKU-SOAP-001','Bath Soap 100g','Personal Care',14,14,18),
            ('SKU-TEA-001','Premium Tea 250g','Beverages',55,7,15),
        ]
        products=[]
        for sku,name,cat,stock,lead,safety in catalog:
            p=db.query(Product).filter(Product.tenant_id==tenant.id,Product.store_id==store.id,Product.sku==sku).first()
            if not p:
                p=Product(tenant_id=tenant.id,store_id=store.id,sku=sku,name=name,category=cat,current_stock=stock,lead_time_days=lead,safety_stock=safety)
                db.add(p);db.flush()
            products.append(p)

        start=datetime.utcnow()-timedelta(days=179)
        for p in products:
            exists=db.query(Sale).filter(Sale.product_id==p.id).first()
            if exists: continue
            base={'Premium Rice 5kg':18,'Sunflower Oil 1L':12,'Toned Milk 1L':25,'Biscuits Family Pack':32,'Bath Soap 100g':16,'Premium Tea 250g':10}[p.name]
            for i in range(180):
                d=start+timedelta(days=i)
                weekly=1.0 + (0.18 if d.weekday() in (5,6) else -0.03)
                seasonal=1.0 + 0.10*math.sin(i/18.0)
                trend=1.0 + i/900.0
                noise=random.uniform(0.82,1.18)
                qty=max(0,round(base*weekly*seasonal*trend*noise,2))
                if i==155 and p.name=='Premium Rice 5kg': qty*=3
                if i==140 and p.name=='Bath Soap 100g': qty*=0.25
                db.add(Sale(tenant_id=tenant.id,store_id=store.id,product_id=p.id,sale_date=d,quantity=qty))
        db.commit()
        print('Demo seed complete')
        print('Login: owner@retailpulse.ai / owner123')
        print(f'Tenant: {tenant.name} | Store: {store.name}')
        print(f'Products: {len(products)} | 180 days of synthetic sales per product')
    finally:
        db.close()

if __name__=='__main__':main()
