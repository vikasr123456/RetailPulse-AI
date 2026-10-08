"""Seed a polished demo catalog with representative products from major global brands.
Demo-only catalog; RetailPulse AI is not affiliated with these brands.
"""
from datetime import datetime, timedelta
import math, random
from app.db import Base, engine, SessionLocal
from app.models import Tenant, Store, User, Product, Sale
from app.auth import hash_password
from sqlalchemy import inspect, text

random.seed(42)
Base.metadata.create_all(bind=engine)
if engine.dialect.name == "postgresql":
    with engine.begin() as conn:
        cols={c["name"] for c in inspect(conn).get_columns("products")}
        additions={
            "company":"VARCHAR(160) DEFAULT 'RetailPulse Demo'",
            "brand":"VARCHAR(160) DEFAULT ''",
            "subcategory":"VARCHAR(160) DEFAULT ''",
            "unit_price":"DOUBLE PRECISION DEFAULT 0",
            "unit_cost":"DOUBLE PRECISION DEFAULT 0",
            "currency":"VARCHAR(8) DEFAULT 'INR'",
            "barcode":"VARCHAR(80) DEFAULT ''",
            "supplier":"VARCHAR(160) DEFAULT ''",
        }
        for name,ddl in additions.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {ddl}"))
db=SessionLocal()

# Reuse or create the demo tenant/store.
tenant=db.query(Tenant).filter(Tenant.slug=="retailpulse-enterprise").first()
if not tenant:
    tenant=Tenant(name="RetailPulse Enterprise Demo",slug="retailpulse-enterprise")
    db.add(tenant); db.flush()
store=db.query(Store).filter(Store.tenant_id==tenant.id).first()
if not store:
    store=Store(tenant_id=tenant.id,name="Global Flagship Store",location="Bengaluru · India")
    db.add(store); db.flush()

users=[
    ("owner@retailpulse.ai","owner123","OWNER"),
    ("manager@retailpulse.ai","manager123","MANAGER"),
    ("staff@retailpulse.ai","staff123","STAFF"),
    ("analyst@retailpulse.ai","analyst123","ANALYST"),
    ("customer@retailpulse.ai","customer123","CUSTOMER"),
]
for email,password,role in users:
    if not db.query(User).filter(User.email==email).first():
        db.add(User(tenant_id=tenant.id,store_id=store.id,email=email,password_hash=hash_password(password),role=role))
db.flush()

# company, brand, product, category, subcategory, price INR, cost INR, lead days, safety
catalog=[
("Apple","Apple","iPhone 15 128GB","Electronics","Smartphones",69900,59000,10,25),
("Apple","Apple","MacBook Air 13 M2","Electronics","Laptops",99900,85000,14,12),
("Apple","Apple","AirPods Pro 2","Electronics","Audio",24900,19000,10,20),
("Samsung","Samsung","Galaxy S24 256GB","Electronics","Smartphones",79999,67500,10,25),
("Samsung","Samsung","Galaxy Tab S9","Electronics","Tablets",76999,64000,12,15),
("Samsung","Samsung","55-inch QLED Smart TV","Electronics","Televisions",89990,74500,14,10),
("Sony","Sony","PlayStation 5 Slim","Electronics","Gaming",54990,46000,14,14),
("Sony","Sony","WH-1000XM5 Headphones","Electronics","Audio",29990,23500,10,18),
("Sony","Sony","Bravia 55-inch 4K TV","Electronics","Televisions",104990,87000,14,10),
("Dell","Dell","Inspiron 15 Laptop","Electronics","Laptops",58990,50000,12,12),
("Dell","Dell","UltraSharp 27 Monitor","Electronics","Monitors",32990,27000,12,10),
("HP","HP","Pavilion 15 Laptop","Electronics","Laptops",64990,55000,12,12),
("HP","HP","LaserJet Pro Printer","Electronics","Printers",23990,19000,10,10),
("Lenovo","Lenovo","IdeaPad Slim 5","Electronics","Laptops",67990,57000,12,12),
("LG","LG","55-inch OLED TV","Electronics","Televisions",119990,99000,14,10),
("LG","LG","Double Door Smart Refrigerator","Appliances","Refrigerators",64990,54000,18,6),
("Xiaomi","Xiaomi","Redmi Note 13 Pro","Electronics","Smartphones",29999,24500,8,25),
("Xiaomi","Xiaomi","Smart Band 8","Electronics","Wearables",3999,3000,8,35),
("Nike","Nike","Air Max 270","Fashion","Footwear",12995,9200,14,18),
("Nike","Nike","Dri-FIT Running T-Shirt","Fashion","Apparel",2495,1600,10,30),
("Adidas","Adidas","Ultraboost Light","Fashion","Footwear",16999,12000,14,18),
("Adidas","Adidas","Essentials Hoodie","Fashion","Apparel",4999,3200,10,25),
("PUMA","PUMA","RS-X Sneakers","Fashion","Footwear",8999,6200,12,20),
("Coca-Cola","Coca-Cola","Coca-Cola 1L","Beverages","Soft Drinks",65,42,4,80),
("PepsiCo","Pepsi","Pepsi 1L","Beverages","Soft Drinks",60,39,4,80),
("Nestlé","Nescafé","Classic Instant Coffee 100g","Grocery","Coffee",260,185,6,45),
("Nestlé","Maggi","2-Minute Noodles 70g","Grocery","Instant Food",15,9,4,100),
("Nestlé","KitKat","KitKat 4 Finger 37.3g","Grocery","Chocolate",40,27,4,70),
("Unilever","Dove","Dove Cream Beauty Bar 100g","Personal Care","Bath & Body",75,48,6,55),
("Unilever","Axe","Axe Deodorant 150ml","Personal Care","Deodorants",210,145,6,45),
("Unilever","Vaseline","Vaseline Intensive Care 200ml","Personal Care","Skin Care",230,155,6,40),
("Procter & Gamble","Ariel","Ariel Matic 2kg","Home Care","Laundry",390,275,6,45),
("Procter & Gamble","Head & Shoulders","Anti-Dandruff Shampoo 340ml","Personal Care","Hair Care",420,290,6,40),
("Procter & Gamble","Gillette","Mach3 Razor System","Personal Care","Grooming",499,340,7,30),
("L'Oréal","L'Oréal Paris","Revitalift Day Cream 50ml","Beauty","Skin Care",699,470,7,30),
("L'Oréal","Garnier","Fructis Shampoo 340ml","Beauty","Hair Care",349,230,6,40),
("Colgate-Palmolive","Colgate","MaxFresh Toothpaste 150g","Personal Care","Oral Care",120,72,5,65),
("Colgate-Palmolive","Palmolive","Shower Gel 250ml","Personal Care","Bath & Body",180,115,5,45),
("Mondelez","Oreo","Oreo Original 120g","Grocery","Biscuits",40,25,4,90),
("Mondelez","Cadbury","Dairy Milk 110g","Grocery","Chocolate",120,78,4,80),
("Kellogg's","Kellogg's","Corn Flakes 300g","Grocery","Breakfast",210,145,5,50),
("Danone","Activia","Activia Yogurt 4x100g","Dairy","Yogurt",180,120,3,45),
("Philips","Philips","Air Fryer 4.1L","Appliances","Kitchen",8999,6800,12,12),
("Bosch","Bosch","Series 4 Washing Machine","Appliances","Laundry",38990,32000,18,6),
("Panasonic","Panasonic","Microwave Oven 25L","Appliances","Kitchen",10990,8500,12,8),
("JBL","JBL","Flip 6 Bluetooth Speaker","Electronics","Audio",11999,8800,10,18),
("Logitech","Logitech","MX Master 3S Mouse","Electronics","Accessories",9995,7200,10,20),
("Amazon","Amazon Basics","USB-C Charging Cable","Electronics","Accessories",599,360,5,80),
("IKEA","IKEA","KALLAX Storage Shelf","Home","Furniture",8990,6100,18,8),
("Dyson","Dyson","V12 Detect Slim","Appliances","Floor Care",54900,44000,18,6),
("Nespresso","Nespresso","Vertuo Pop Coffee Machine","Appliances","Coffee Machines",15990,12500,12,8),
]

# Remove existing demo catalog and dependent records for a clean, repeatable seed.
from app.models import Forecast, ForecastValue, Alert
forecast_ids=[x[0] for x in db.query(Forecast.id).filter(Forecast.tenant_id==tenant.id,Forecast.store_id==store.id).all()]
if forecast_ids:
    db.query(ForecastValue).filter(ForecastValue.forecast_id.in_(forecast_ids)).delete(synchronize_session=False)
db.query(Forecast).filter(Forecast.tenant_id==tenant.id,Forecast.store_id==store.id).delete(synchronize_session=False)
db.query(Alert).filter(Alert.tenant_id==tenant.id,Alert.store_id==store.id).delete(synchronize_session=False)
db.query(Sale).filter(Sale.tenant_id==tenant.id,Sale.store_id==store.id).delete(synchronize_session=False)
db.query(Product).filter(Product.tenant_id==tenant.id,Product.store_id==store.id).delete(synchronize_session=False)
db.commit()

start=datetime.utcnow()-timedelta(days=364)
for idx,(company,brand,name,category,subcat,price,cost,lead,safety) in enumerate(catalog,1):
    sku=f"RP-{idx:04d}"
    p=Product(tenant_id=tenant.id,store_id=store.id,sku=sku,name=name,company=company,brand=brand,
              category=category,subcategory=subcat,unit_price=price,unit_cost=cost,currency="INR",
              barcode=f"890{idx:010d}",supplier=f"{company} Authorized Distribution",current_stock=safety*2,
              lead_time_days=lead,safety_stock=safety)
    db.add(p); db.flush()
    base=max(4, int(90000/max(price,100)))
    # create one year of daily demand with trend + weekly + mild annual seasonality
    for d in range(365):
        date=start+timedelta(days=d)
        weekly=1+0.14*math.sin(2*math.pi*d/7)
        annual=1+0.10*math.sin(2*math.pi*d/365+idx/7)
        weekend=1.10 if date.weekday()>=5 else 1.0
        trend=1+d/2500
        qty=max(0,int(round(base*weekly*annual*weekend*trend*random.uniform(.88,1.12))))
        db.add(Sale(tenant_id=tenant.id,store_id=store.id,product_id=p.id,sale_date=date,quantity=qty))

db.commit(); db.close()
print(f"Seeded {len(catalog)} representative international-brand products and 365 days of sales.")
print("Demo catalog is for product demonstration only; RetailPulse AI is not affiliated with the listed brands.")
print("OWNER owner@retailpulse.ai / owner123")
