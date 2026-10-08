
from datetime import datetime
import json
import io
import pandas as pd
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, inspect, text
from .db import Base, engine, get_db
from .models import Tenant, Store, User, Product, Sale, Forecast, ForecastValue, Alert, AuditLog
from .schemas import LoginRequest, RegisterRequest, ForecastRequest, ScenarioRequest, CopilotRequest
from .auth import hash_password, verify_password, create_token, require_auth, require_roles, ROLES
from .services import generate_forecast, restock_for_product
from .data_quality.pipeline import normalize_columns, detect_columns, score_quality, clean_dataframe, forecast_readiness
from .inventory.service import inventory_dashboard, inventory_position, update_stock
from .inventory.advisor import advise, restock_center
from .scenarios.service import get_product as get_scenario_product, calculate_scenario, scenario_compare
from .dashboard.service import dashboard_data
from .alerts.service import build_alerts
from .reports.service import report_summary
from .forecasting.arima import run_arima_pipeline, prepare_series as arima_prepare_series
from .forecasting.lstm import run_lstm_pipeline, prepare_series as lstm_prepare_series
from .forecasting.evaluation import evaluate_models
from .forecasting.performance import cache_key, get as cache_get, put as cache_put, clear as cache_clear
from .seasonality.analysis import prepare_daily, seasonality_report, anomaly_report


PRODUCT_MIGRATION_COLUMNS = {
    "company": "VARCHAR(160) DEFAULT 'RetailPulse Demo'",
    "brand": "VARCHAR(160) DEFAULT ''",
    "subcategory": "VARCHAR(160) DEFAULT ''",
    "unit_price": "DOUBLE PRECISION DEFAULT 0",
    "unit_cost": "DOUBLE PRECISION DEFAULT 0",
    "currency": "VARCHAR(8) DEFAULT 'INR'",
    "barcode": "VARCHAR(80) DEFAULT ''",
    "supplier": "VARCHAR(160) DEFAULT ''",
}

def ensure_enterprise_schema():
    """Create missing tables/columns so an older RetailPulse DB can be upgraded in place."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        inspector = inspect(conn)
        if "products" not in inspector.get_table_names():
            Base.metadata.create_all(bind=conn)
            inspector = inspect(conn)
        columns = {c["name"] for c in inspector.get_columns("products")}
        for name, ddl in PRODUCT_MIGRATION_COLUMNS.items():
            if name not in columns:
                conn.execute(text(f"ALTER TABLE products ADD COLUMN {name} {ddl}"))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS ix_products_tenant_store_company ON products (tenant_id, store_id, company)",
            "CREATE INDEX IF NOT EXISTS ix_products_tenant_store_brand ON products (tenant_id, store_id, brand)",
            "CREATE INDEX IF NOT EXISTS ix_sales_tenant_store_date ON sales (tenant_id, store_id, sale_date)",
        ):
            conn.execute(text(stmt))

ensure_enterprise_schema()

app = FastAPI(title="RetailPulse AI API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def scoped_products(db, user):
    return db.query(Product).filter(
        Product.tenant_id == user["tenant_id"],
        Product.store_id == user["store_id"]
    )

def scoped_sales(db, user):
    return db.query(Sale).filter(
        Sale.tenant_id == user["tenant_id"],
        Sale.store_id == user["store_id"]
    )

@app.get("/health")
@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status":"healthy","database":"connected","forecast_engine":"ARIMA + LSTM","phase":"enterprise"}

@app.get("/api/v1/system/diagnostics")
def system_diagnostics(db: Session = Depends(get_db), user=Depends(require_auth)):
    """Safe, tenant-scoped health information used by the Data Intelligence UI."""
    product_count = scoped_products(db, user).count()
    sales_count = scoped_sales(db, user).count()
    sales_scope = scoped_sales(db, user)
    date_start = sales_scope.with_entities(func.min(Sale.sale_date)).scalar()
    date_end = sales_scope.with_entities(func.max(Sale.sale_date)).scalar()
    inspector = inspect(engine)
    columns = {c["name"] for c in inspector.get_columns("products")} if "products" in inspector.get_table_names() else set()
    required = {"company","brand","subcategory","unit_price","unit_cost","currency","barcode","supplier"}
    return {
        "database": "postgresql" if engine.dialect.name == "postgresql" else engine.dialect.name,
        "schema_ready": required.issubset(columns),
        "products": product_count,
        "sales": sales_count,
        "date_start": date_start.strftime("%Y-%m-%d") if date_start else None,
        "date_end": date_end.strftime("%Y-%m-%d") if date_end else None,
        "tables": sorted(inspector.get_table_names()),
    }

@app.post("/api/v1/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email==req.email).first()
    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {
        "access_token": create_token(user),
        "role": user.role,
        "email": user.email,
        "tenant_id": user.tenant_id,
        "store_id": user.store_id
    }

@app.post("/api/v1/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create a self-service demo workspace account. New accounts start as CUSTOMER.

    OWNERs can promote users later from Settings & Access. This keeps public
    registration from granting administrative privileges.
    """
    email = req.email.strip().lower()
    if not email or "@" not in email or len(email) > 255:
        raise HTTPException(400, "Enter a valid work email address")
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if req.password != req.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists. Please sign in.")

    # The seeded demo tenant/store are the default workspace for self-service
    # registration. In production this should be replaced by an invite flow.
    tenant = db.query(Tenant).order_by(Tenant.id.asc()).first()
    if not tenant:
        raise HTTPException(503, "No workspace is available for registration")
    store = db.query(Store).filter(Store.tenant_id == tenant.id).order_by(Store.id.asc()).first()

    new_user = User(
        tenant_id=tenant.id,
        store_id=store.id if store else None,
        email=email,
        password_hash=hash_password(req.password),
        role="CUSTOMER",
        is_active=True,
    )
    db.add(new_user)
    db.flush()
    db.commit()
    return {
        "access_token": create_token(new_user),
        "role": new_user.role,
        "email": new_user.email,
        "tenant_id": new_user.tenant_id,
        "store_id": new_user.store_id,
        "message": "Account created successfully",
    }

@app.get("/api/v1/auth/me")
def me(user=Depends(require_auth), db:Session=Depends(get_db)):
    u=db.query(User).filter(User.id==user["user_id"], User.tenant_id==user["tenant_id"]).first()
    if not u: raise HTTPException(404,"User not found")
    tenant=db.query(Tenant).get(u.tenant_id)
    store=db.query(Store).get(u.store_id) if u.store_id else None
    return {
        "id":u.id,"email":u.email,"role":u.role,
        "tenant":{"id":tenant.id,"name":tenant.name,"slug":tenant.slug},
        "store":None if not store else {"id":store.id,"name":store.name,"location":store.location}
    }

@app.get("/api/v1/auth/permissions")
def permissions(user=Depends(require_auth)):
    role=user["role"]
    matrix={
        "OWNER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot","settings","users"],
        "MANAGER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot"],
        "STAFF":["dashboard","products","inventory","restock","alerts"],
        "ANALYST":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","reports","copilot"],
        "CUSTOMER":["products","availability","copilot"]
    }
    return {"role":role,"permissions":matrix[role]}


@app.get("/api/v1/settings/overview")
def settings_overview(db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    tenant=db.query(Tenant).filter(Tenant.id==user["tenant_id"]).first()
    stores=db.query(Store).filter(Store.tenant_id==user["tenant_id"]).all()
    users=db.query(User).filter(User.tenant_id==user["tenant_id"]).all()
    return {
        "tenant":{"id":tenant.id,"name":tenant.name,"slug":tenant.slug},
        "stores":[{"id":s.id,"name":s.name,"location":s.location} for s in stores],
        "users":[{"id":u.id,"email":u.email,"role":u.role,"store_id":u.store_id,"active":u.is_active} for u in users],
        "roles":sorted(ROLES),
        "permission_matrix":{
            "OWNER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot","settings","users"],
            "MANAGER":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","inventory","restock","scenarios","alerts","reports","copilot"],
            "STAFF":["dashboard","products","inventory","restock","alerts"],
            "ANALYST":["dashboard","products","data_upload","forecasts","arima","lstm","model_center","seasonality","reports","copilot"],
            "CUSTOMER":["products","availability","copilot"]
        }
    }

@app.get("/api/v1/tenant")
def tenant_info(user=Depends(require_auth), db:Session=Depends(get_db)):
    t=db.query(Tenant).filter(Tenant.id==user["tenant_id"]).first()
    stores=db.query(Store).filter(Store.tenant_id==t.id).all()
    return {"id":t.id,"name":t.name,"slug":t.slug,
            "stores":[{"id":s.id,"name":s.name,"location":s.location} for s in stores]}

@app.get("/api/v1/users")
def users(db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    rows=db.query(User).filter(User.tenant_id==user["tenant_id"]).all()
    return [{"id":u.id,"email":u.email,"role":u.role,"store_id":u.store_id,"active":u.is_active} for u in rows]

@app.post("/api/v1/users")
def create_user(payload:dict, db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    email=str(payload.get("email","")).strip().lower()
    role=str(payload.get("role","STAFF")).upper()
    password=str(payload.get("password",""))
    store_id=payload.get("store_id")
    if not email or len(password)<8 or role not in ROLES:
        raise HTTPException(400,"Email, password (8+ characters) and valid role are required")
    if db.query(User).filter(User.email==email).first():
        raise HTTPException(409,"User already exists")
    if store_id is not None and not db.query(Store).filter(Store.id==store_id,Store.tenant_id==user["tenant_id"]).first():
        raise HTTPException(400,"Store does not belong to this tenant")
    u=User(tenant_id=user["tenant_id"],store_id=store_id,email=email,password_hash=hash_password(password),role=role)
    db.add(u)
    db.add(AuditLog(tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],action="USER_CREATED",details=json.dumps({"email":email,"role":role})))
    db.commit()
    return {"id":u.id,"email":u.email,"role":u.role,"store_id":u.store_id}

@app.get("/api/v1/reports/summary")
def reports_summary(days:int=30, db:Session=Depends(get_db),
                    user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    try:
        return report_summary(
            db,
            user["tenant_id"],
            user["store_id"],
            days
        )
    except ValueError as e:
        raise HTTPException(400, str(e))



@app.get("/api/v1/reports/periodic")
def periodic_report(period: str = "daily", db: Session = Depends(get_db),
                    user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    """Chart-ready daily/weekly/monthly/yearly reports anchored to the uploaded dataset."""
    period = period.lower().strip()
    if period not in {"daily", "weekly", "monthly", "yearly"}:
        raise HTTPException(400, "period must be daily, weekly, monthly or yearly")

    rows = scoped_sales(db, user).order_by(Sale.sale_date).all()
    if not rows:
        return {
            "period": period,
            "anchor_date": None,
            "kpis": {"total_units": 0, "average_units": 0, "peak_units": 0,
                     "growth_pct": None, "records": 0},
            "series": [],
            "top_products": []
        }

    df = pd.DataFrame([
        {"date": r.sale_date, "quantity": float(r.quantity), "product_id": r.product_id}
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return {
            "period": period, "anchor_date": None,
            "kpis": {"total_units": 0, "average_units": 0, "peak_units": 0,
                     "growth_pct": None, "records": 0},
            "series": [], "top_products": []
        }

    anchor = pd.Timestamp(df["date"].max()).normalize()

    if period == "daily":
        start = anchor - pd.Timedelta(days=29)
        bucketed = df.assign(bucket=df["date"].dt.normalize())
        expected = pd.date_range(start, anchor, freq="D")
        grouped = bucketed.groupby("bucket")["quantity"].sum()
        series = [
            {"label": d.strftime("%Y-%m-%d"),
             "units": round(float(grouped.get(d, 0)), 2)}
            for d in expected
        ]
    elif period == "weekly":
        start = anchor - pd.Timedelta(weeks=11)
        iso = df["date"].dt.isocalendar()
        df["bucket"] = [
            f"{int(y)}-W{int(w):02d}" for y, w in zip(iso.year, iso.week)
        ]
        grouped = df.groupby("bucket")["quantity"].sum()
        start_week = start.to_period("W-SUN").start_time
        series = []
        for i in range(12):
            d = start_week + pd.Timedelta(weeks=i)
            iso_year = int(d.isocalendar().year)
            iso_week = int(d.isocalendar().week)
            key = f"{iso_year}-W{iso_week:02d}"
            series.append({"label": key, "units": round(float(grouped.get(key, 0)), 2)})
    elif period == "monthly":
        start = anchor.to_period("M") - 11
        df["bucket"] = df["date"].dt.to_period("M").astype(str)
        grouped = df.groupby("bucket")["quantity"].sum()
        months = pd.period_range(start=start, end=anchor.to_period("M"), freq="M")
        series = [
            {"label": str(m), "units": round(float(grouped.get(str(m), 0)), 2)}
            for m in months
        ]
    else:
        start_year = anchor.year - 4
        df["bucket"] = df["date"].dt.year.astype(str)
        grouped = df.groupby("bucket")["quantity"].sum()
        series = [
            {"label": str(y), "units": round(float(grouped.get(str(y), 0)), 2)}
            for y in range(start_year, anchor.year + 1)
        ]

    values = [float(x["units"]) for x in series]
    total = sum(values)
    avg = total / len(values) if values else 0
    peak = max(values) if values else 0

    # Compare the last half of the report periods with the first half.
    growth = None
    if len(values) >= 4:
        half = len(values) // 2
        old = sum(values[:half]) / max(half, 1)
        new = sum(values[half:]) / max(len(values) - half, 1)
        if old:
            growth = round((new - old) / old * 100, 2)

    product_ids = df.groupby("product_id")["quantity"].sum().sort_values(ascending=False).head(10)
    product_rows = []
    for pid, units in product_ids.items():
        p = db.query(Product).filter(Product.id == int(pid)).first()
        product_rows.append({
            "product": p.name if p else f"Product {pid}",
            "units": round(float(units), 2)
        })

    # Category sales breakdown for the selected report window.
    product_map = {
        p.id: p for p in db.query(Product).filter(
            Product.tenant_id == user["tenant_id"],
            Product.store_id == user["store_id"]
        ).all()
    }
    category_totals = {}
    for row in df.itertuples(index=False):
        product = product_map.get(int(row.product_id))
        category = (product.category if product and product.category else "Other").strip() or "Other"
        category_totals[category] = category_totals.get(category, 0) + float(row.quantity)
    categories = [
        {"category": category, "units": round(units, 2)}
        for category, units in sorted(category_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        "period": period,
        "anchor_date": anchor.strftime("%Y-%m-%d"),
        "kpis": {
            "total_units": round(total, 2),
            "average_units": round(avg, 2),
            "peak_units": round(peak, 2),
            "growth_pct": growth,
            "records": int(len(df))
        },
        "series": series,
        "top_products": product_rows,
        "categories": categories
    }

@app.get("/api/v1/alerts")
def alerts(db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    return build_alerts(db,user["tenant_id"],user["store_id"])

@app.get("/api/v1/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","STAFF","ANALYST"))):
    return dashboard_data(db, user["tenant_id"], user["store_id"])

@app.get("/api/v1/products")
def products(db: Session=Depends(get_db), user=Depends(require_auth)):
    return scoped_products(db,user).order_by(Product.name).all()

@app.get("/api/v1/products/{product_id}")
def product(product_id:int, db:Session=Depends(get_db), user=Depends(require_auth)):
    p=scoped_products(db,user).filter(Product.id==product_id).first()
    if not p: raise HTTPException(404,"Product not found")
    inv=inventory_position(db,product_id,user["tenant_id"],user["store_id"])
    return {
        "id":p.id,"sku":p.sku,"name":p.name,"company":p.company,"brand":p.brand,
        "category":p.category,"subcategory":p.subcategory,"unit_price":p.unit_price,
        "unit_cost":p.unit_cost,"currency":p.currency,"barcode":p.barcode,"supplier":p.supplier,
        "current_stock":p.current_stock,"lead_time_days":p.lead_time_days,
        "safety_stock":p.safety_stock,"inventory":inv
    }

@app.post("/api/v1/products")
def create_product(payload:dict, db:Session=Depends(get_db),
                   user=Depends(require_roles("OWNER","MANAGER"))):
    sku=str(payload.get("sku","")).strip()
    name=str(payload.get("name","")).strip()
    category=str(payload.get("category","General")).strip()
    if not sku or not name: raise HTTPException(400,"SKU and product name are required")
    if scoped_products(db,user).filter(Product.sku==sku).first():
        raise HTTPException(409,"SKU already exists in this store")
    p=Product(
        tenant_id=user["tenant_id"],store_id=user["store_id"],sku=sku,name=name,
        company=str(payload.get("company","RetailPulse Demo")),
        brand=str(payload.get("brand","")),category=category,
        subcategory=str(payload.get("subcategory","")),
        unit_price=float(payload.get("unit_price",0)),unit_cost=float(payload.get("unit_cost",0)),
        currency=str(payload.get("currency","INR")),barcode=str(payload.get("barcode","")),
        supplier=str(payload.get("supplier","")),
        current_stock=float(payload.get("current_stock",0)),
        lead_time_days=int(payload.get("lead_time_days",7)),
        safety_stock=float(payload.get("safety_stock",10))
    )
    if p.current_stock<0 or p.lead_time_days<0 or p.safety_stock<0:
        raise HTTPException(400,"Stock, lead time and safety stock cannot be negative")
    db.add(p); db.commit(); db.refresh(p)
    return p

@app.patch("/api/v1/products/{product_id}")
def update_product(product_id:int,payload:dict,db:Session=Depends(get_db),
                   user=Depends(require_roles("OWNER","MANAGER"))):
    p=scoped_products(db, user).filter(Product.id==product_id).first()
    if not p: raise HTTPException(404,"Product not found")
    for field in ["sku","name","company","brand","category","subcategory","currency","barcode","supplier"]:
        if field in payload and str(payload[field]).strip():
            setattr(p,field,str(payload[field]).strip())
    for field in ["current_stock","safety_stock","unit_price","unit_cost"]:
        if field in payload:
            value=float(payload[field])
            if value<0: raise HTTPException(400,f"{field} cannot be negative")
            setattr(p,field,value)
    if "lead_time_days" in payload:
        value=int(payload["lead_time_days"])
        if value<0: raise HTTPException(400,"lead_time_days cannot be negative")
        p.lead_time_days=value
    db.commit();db.refresh(p)
    return p

@app.get("/api/v1/inventory")
def inventory(db:Session=Depends(get_db),user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    return inventory_dashboard(db,user["tenant_id"],user["store_id"])

@app.get("/api/v1/inventory/{product_id}")
def inventory_product(product_id:int,db:Session=Depends(get_db),user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    x=inventory_position(db,product_id,user["tenant_id"],user["store_id"])
    if not x: raise HTTPException(404,"Product not found")
    return x

@app.patch("/api/v1/inventory/{product_id}/stock")
def change_stock(product_id:int,payload:dict,db:Session=Depends(get_db),
                 user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    if "stock" not in payload: raise HTTPException(400,"stock is required")
    try: x=update_stock(db,product_id,user["tenant_id"],user["store_id"],float(payload["stock"]))
    except ValueError as e: raise HTTPException(400,str(e))
    if not x: raise HTTPException(404,"Product not found")
    return x

@app.post("/api/v1/data/reset")
def reset_dataset(db:Session=Depends(get_db), user=Depends(require_roles("OWNER"))):
    """Delete the current store's products and all dependent retail/model data.

    Tenant/store scoped and intentionally OWNER-only because this is destructive.
    Audit history is preserved.
    """
    tenant_id=user["tenant_id"]
    store_id=user["store_id"]
    if store_id is None:
        raise HTTPException(400,"No store is assigned to this account.")

    product_ids=[x[0] for x in db.query(Product.id).filter(
        Product.tenant_id==tenant_id, Product.store_id==store_id
    ).all()]

    forecast_ids=[x[0] for x in db.query(Forecast.id).filter(
        Forecast.tenant_id==tenant_id, Forecast.store_id==store_id
    ).all()]
    if forecast_ids:
        db.query(ForecastValue).filter(ForecastValue.forecast_id.in_(forecast_ids)).delete(synchronize_session=False)
    db.query(Forecast).filter(
        Forecast.tenant_id==tenant_id, Forecast.store_id==store_id
    ).delete(synchronize_session=False)
    db.query(Sale).filter(
        Sale.tenant_id==tenant_id, Sale.store_id==store_id
    ).delete(synchronize_session=False)
    db.query(Alert).filter(
        Alert.tenant_id==tenant_id, Alert.store_id==store_id
    ).delete(synchronize_session=False)
    deleted=db.query(Product).filter(
        Product.tenant_id==tenant_id, Product.store_id==store_id
    ).delete(synchronize_session=False)

    db.add(AuditLog(
        tenant_id=tenant_id, store_id=store_id, user_id=user["user_id"],
        action="DATASET_RESET",
        details=json.dumps({"products_deleted":deleted})
    ))
    db.commit()
    return {"status":"success","products_deleted":int(deleted),
            "message":"Current store dataset was cleared. You can now upload a new dataset."}

@app.post("/api/v1/data/upload")
async def upload(file: UploadFile=File(...), db:Session=Depends(get_db),
                 user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if not file.filename.lower().endswith((".csv",".xlsx",".xls")):
        raise HTTPException(400,"Only CSV and Excel files are supported.")
    data=await file.read()
    try:
        source=io.BytesIO(data)
        df=pd.read_csv(source) if file.filename.lower().endswith(".csv") else pd.read_excel(source)
    except Exception as exc:
        raise HTTPException(400,f"The uploaded file could not be read: {exc}")

    if df.empty:
        raise HTTPException(400,"The uploaded file contains no records.")

    df=normalize_columns(df)
    mapping,confidence=detect_columns(df)
    quality=score_quality(df,mapping)
    cleaned,duplicates_removed=clean_dataframe(df,mapping)
    readiness=forecast_readiness(cleaned,mapping)

    if not mapping.get("date") or not mapping.get("product") or not mapping.get("quantity"):
        return {
            "status":"needs_mapping",
            "filename":file.filename,
            "rows":len(df),
            "columns":list(df.columns),
            "mapping":mapping,
            "confidence":confidence,
            "quality":quality,
            "cleaned_rows":len(cleaned),
            "duplicates_removed":duplicates_removed,
            "readiness":readiness
        }

    inserted=0
    for name,group in cleaned.groupby("_product"):
        name=str(name)
        p=scoped_products(db,user).filter(Product.name==name).first()
        if not p:
            category="Imported"
            if mapping.get("category") and len(group):
                category=str(group.iloc[0][mapping["category"]])
            p=Product(
                tenant_id=user["tenant_id"],store_id=user["store_id"],
                sku=f"SKU-{abs(hash(name))%100000}",name=name,category=category
            )
            db.add(p); db.flush()

        for _,row in group.iterrows():
            db.add(Sale(
                tenant_id=user["tenant_id"],store_id=user["store_id"],product_id=p.id,
                sale_date=pd.Timestamp(row["_date"]).to_pydatetime(),quantity=float(row["_quantity"])
            ))
            inserted+=1

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="DATA_UPLOADED",
        details=json.dumps({
            "filename":file.filename,"raw_rows":len(df),"clean_rows":len(cleaned),
            "records_inserted":inserted,"duplicates_removed":duplicates_removed,
            "quality_score":quality["score"]
        })
    ))
    db.commit()

    return {
        "status":"success",
        "filename":file.filename,
        "raw_rows":len(df),
        "cleaned_rows":len(cleaned),
        "records_inserted":inserted,
        "products_detected":int(cleaned["_product"].nunique()),
        "mapping":mapping,
        "confidence":confidence,
        "quality":quality,
        "duplicates_removed":duplicates_removed,
        "readiness":readiness
    }

@app.post("/api/v1/data/replace")
async def replace_dataset(file: UploadFile=File(...), db:Session=Depends(get_db),
                          user=Depends(require_roles("OWNER"))):
    """Validate/analyze a dataset first, then atomically replace the store data."""
    if not file.filename or not file.filename.lower().endswith((".csv",".xlsx",".xls")):
        raise HTTPException(400,"Only CSV and Excel files are supported.")

    data=await file.read()
    if len(data)>25*1024*1024:
        raise HTTPException(400,"Dataset is too large. Maximum size is 25 MB.")
    try:
        source=io.BytesIO(data)
        df=pd.read_csv(source) if file.filename.lower().endswith(".csv") else pd.read_excel(source)
    except Exception as exc:
        raise HTTPException(400,f"The uploaded dataset could not be read: {exc}")

    if df.empty:
        raise HTTPException(400,"The uploaded dataset contains no records.")

    df=normalize_columns(df)
    mapping,confidence=detect_columns(df)
    quality=score_quality(df,mapping)
    cleaned,duplicates_removed=clean_dataframe(df,mapping)
    readiness=forecast_readiness(cleaned,mapping)

    required=(mapping.get("date"),mapping.get("product"),mapping.get("quantity"))
    if not all(required):
        return {
            "status":"needs_mapping", "filename":file.filename, "raw_rows":len(df),
            "columns":list(df.columns), "mapping":mapping, "confidence":confidence,
            "quality":quality, "cleaned_rows":len(cleaned),
            "duplicates_removed":duplicates_removed, "readiness":readiness,
            "message":"Dataset was analyzed but not imported because required columns were not detected."
        }
    if cleaned.empty:
        raise HTTPException(400,"No valid records remain after cleaning. Nothing was replaced.")

    tenant_id=user["tenant_id"]; store_id=user["store_id"]
    # Refuse unsafe writes if an older database schema is still in place.
    inspector=inspect(engine)
    product_columns={c["name"] for c in inspector.get_columns("products")}
    missing=sorted(set(PRODUCT_MIGRATION_COLUMNS)-product_columns)
    if missing:
        raise HTTPException(500, "Database schema is outdated. Restart the backend so the automatic migration can run, or execute scripts/migrate_enterprise_db.py. Missing columns: " + ", ".join(missing))
    # Clear dependent data only after validation has succeeded.
    forecast_ids=[x[0] for x in db.query(Forecast.id).filter(
        Forecast.tenant_id==tenant_id, Forecast.store_id==store_id
    ).all()]
    if forecast_ids:
        db.query(ForecastValue).filter(ForecastValue.forecast_id.in_(forecast_ids)).delete(synchronize_session=False)
    db.query(Forecast).filter(Forecast.tenant_id==tenant_id, Forecast.store_id==store_id).delete(synchronize_session=False)
    db.query(Sale).filter(Sale.tenant_id==tenant_id, Sale.store_id==store_id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.tenant_id==tenant_id, Alert.store_id==store_id).delete(synchronize_session=False)
    db.query(Product).filter(Product.tenant_id==tenant_id, Product.store_id==store_id).delete(synchronize_session=False)

    inserted=0
    product_count=0
    for name,group in cleaned.groupby("_product"):
        name=str(name).strip()
        category="Imported"
        if mapping.get("category") and len(group):
            val=group.iloc[0].get(mapping["category"])
            if pd.notna(val) and str(val).strip(): category=str(val).strip()

        sku=f"SKU-{abs(hash(name))%100000}"
        stock=0.0
        if mapping.get("inventory") and len(group):
            vals=pd.to_numeric(group[mapping["inventory"]],errors="coerce").dropna()
            if len(vals): stock=float(vals.iloc[-1])
        # Give imported products sensible operational defaults when the dataset
        # does not contain explicit planning parameters.
        daily_avg=float(pd.to_numeric(group["_quantity"],errors="coerce").mean() or 0)
        safety=max(10.0, round(daily_avg*2.0, 2))

        brand=""
        company="Imported Catalog"
        if mapping.get("brand") and len(group):
            v=group.iloc[0].get(mapping["brand"]); brand="" if pd.isna(v) else str(v).strip()
        if mapping.get("company") and len(group):
            v=group.iloc[0].get(mapping["company"]); company="Imported Catalog" if pd.isna(v) or not str(v).strip() else str(v).strip()
        p=Product(tenant_id=tenant_id,store_id=store_id,sku=sku,name=name,
                  company=company,brand=brand,category=category,current_stock=max(0,stock),
                  lead_time_days=7,safety_stock=safety)
        db.add(p); db.flush()
        product_count+=1
        for _,row in group.iterrows():
            db.add(Sale(tenant_id=tenant_id,store_id=store_id,product_id=p.id,
                        sale_date=pd.Timestamp(row["_date"]).to_pydatetime(),quantity=float(row["_quantity"])))
            inserted+=1

    # Produce actual dataset-level analysis for the UI.
    date_series=pd.to_datetime(cleaned["_date"],errors="coerce")
    quantities=pd.to_numeric(cleaned["_quantity"],errors="coerce")
    grouped=cleaned.groupby("_product")["_quantity"].sum().sort_values(ascending=False)
    analysis={
        "products":int(product_count),
        "sales_records":int(inserted),
        "total_units":round(float(quantities.sum()),2),
        "date_start":date_series.min().strftime("%Y-%m-%d"),
        "date_end":date_series.max().strftime("%Y-%m-%d"),
        "top_products":[{"product":str(k),"units":round(float(v),2)} for k,v in grouped.head(10).items()],
        "average_daily_units":round(float(grouped.sum()/max((date_series.max()-date_series.min()).days+1,1)),2),
        "forecast_ready_products":int(sum(
            (g["_date"].max()-g["_date"].min()).days>=45
            for _,g in cleaned.groupby("_product")
        ))
    }

    db.add(AuditLog(tenant_id=tenant_id,store_id=store_id,user_id=user["user_id"],
        action="DATASET_REPLACED",details=json.dumps({
            "filename":file.filename,"raw_rows":len(df),"clean_rows":len(cleaned),
            "products":product_count,"records_inserted":inserted,
            "duplicates_removed":duplicates_removed,"quality_score":quality["score"]
        })))
    db.commit()
    cache_clear()
    return {
        "status":"success", "mode":"replace", "filename":file.filename,
        "raw_rows":len(df), "cleaned_rows":len(cleaned),
        "records_inserted":inserted, "products_detected":product_count,
        "mapping":mapping,"confidence":confidence,"quality":quality,
        "duplicates_removed":duplicates_removed,"readiness":readiness,
        "analysis":analysis,
        "message":"Dataset analyzed and imported. Previous store products and dependent forecast/sales data were replaced."
    }

@app.post("/api/v1/evaluation/compare")
def compare_models(req:ForecastRequest, db:Session=Depends(get_db),
                   user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    product=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not product:
        raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==req.product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()

    cache_id=cache_key(product.id, rows, req.horizon, "EVALUATION")
    result=cache_get(cache_id)
    try:
        if result is None:
            result=evaluate_models(rows,req.horizon)
            cache_put(cache_id,result)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"Model evaluation failed: {e}")

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="MODEL_COMPARISON_RUN",
        details=json.dumps({
            "product_id":req.product_id,
            "winner":result["winner"],
            "primary_metric":result["primary_metric"]
        })
    ))
    db.commit()

    return {
        "product_id":product.id,
        "product":product.name,
        "sku":product.sku,
        **result
    }

@app.post("/api/v1/forecast/lstm")
def lstm_forecast_endpoint(req:ForecastRequest, db:Session=Depends(get_db),
                           user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if req.horizon<1 or req.horizon>365:
        raise HTTPException(400,"Horizon must be 1-365 days.")
    product=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not product: raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==req.product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()
    if not rows: raise HTTPException(400,"No sales history exists for this product.")

    cache_id=cache_key(product.id, rows, req.horizon, "LSTM")
    result=cache_get(cache_id)
    df=pd.DataFrame([{"sale_date":r.sale_date,"quantity":r.quantity} for r in rows])
    try:
        if result is None:
            series=lstm_prepare_series(df)
            result=run_lstm_pipeline(series,req.horizon)
            cache_put(cache_id,result)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"LSTM pipeline failed: {e}")

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="LSTM_PIPELINE_RUN",
        details=json.dumps({
            "product_id":req.product_id,
            "horizon":req.horizon,
            "lookback":result["lookback"],
            "mape":result["metrics"]["mape"]
        })
    ))
    db.commit()
    return {"product_id":product.id,"product":product.name,"sku":product.sku,**result}

@app.post("/api/v1/forecast/arima")
def arima_forecast_endpoint(req:ForecastRequest, db:Session=Depends(get_db),
                            user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if req.horizon < 1 or req.horizon > 365:
        raise HTTPException(400,"Horizon must be 1-365 days.")
    product=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not product:
        raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==req.product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()

    if not rows:
        raise HTTPException(400,"No sales history exists for this product.")

    cache_id=cache_key(product.id, rows, req.horizon, "ARIMA")
    result=cache_get(cache_id)
    df=pd.DataFrame([{"sale_date":r.sale_date,"quantity":r.quantity} for r in rows])
    try:
        if result is None:
            series=arima_prepare_series(df)
            result=run_arima_pipeline(series,req.horizon)
            cache_put(cache_id,result)
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"ARIMA pipeline failed: {e}")

    db.add(AuditLog(
        tenant_id=user["tenant_id"],store_id=user["store_id"],user_id=user["user_id"],
        action="ARIMA_PIPELINE_RUN",
        details=json.dumps({
            "product_id":req.product_id,
            "horizon":req.horizon,
            "order":result["order"],
            "mape":result["metrics"]["mape"]
        })
    ))
    db.commit()

    return {
        "product_id":product.id,
        "product":product.name,
        "sku":product.sku,
        **result
    }

@app.get("/api/v1/seasonality")
def seasonality(product_id:int, db:Session=Depends(get_db),
                user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    product=scoped_products(db,user).filter(Product.id==product_id).first()
    if not product: raise HTTPException(404,"Product not found.")
    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()
    try:
        series=prepare_daily(rows)
        report=seasonality_report(series)
    except ValueError as e: raise HTTPException(400,str(e))
    return {"product_id":product.id,"product":product.name,**report}

@app.get("/api/v1/anomalies")
def anomalies(product_id:int, db:Session=Depends(get_db),
              user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    product=scoped_products(db,user).filter(Product.id==product_id).first()
    if not product: raise HTTPException(404,"Product not found.")
    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()
    try:
        series=prepare_daily(rows)
        report=anomaly_report(series)
    except ValueError as e: raise HTTPException(400,str(e))
    return {"product_id":product.id,"product":product.name,**report}

@app.get("/api/v1/forecast/studio")
def forecast_studio(product_id:int, horizon:int=30, model:str="AUTO",
                     db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if horizon < 1 or horizon > 365:
        raise HTTPException(400,"Horizon must be 1-365 days.")

    product=scoped_products(db,user).filter(Product.id==product_id).first()
    if not product:
        raise HTTPException(404,"Product not found.")

    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==user["tenant_id"],
        Sale.store_id==user["store_id"]
    ).order_by(Sale.sale_date).all()

    if not rows:
        raise HTTPException(400,"No sales history exists for this product.")

    df=pd.DataFrame([{"sale_date":r.sale_date,"quantity":r.quantity} for r in rows])

    # Cache by the active dataset signature. AUTO evaluates only on a cache miss.
    requested_model=model.upper()
    cache_id=cache_key(product.id, rows, horizon, requested_model)
    cached=cache_get(cache_id)
    selected=requested_model
    comparison=None
    if cached is not None:
        selected=cached["selected_model"]
        result=cached["result"]
        comparison=cached.get("comparison")
    else:
        if selected=="AUTO":
            try:
                comparison=evaluate_models(rows,horizon,include_forecast=True)
                winner_payload=comparison.pop("_winner_forecast")
                selected=winner_payload["model"]
                result=winner_payload
            except Exception as e:
                raise HTTPException(400,f"Model selection failed: {e}")
        else:
            try:
                if selected=="ARIMA":
                    series=arima_prepare_series(df)
                    result=run_arima_pipeline(series,horizon)
                elif selected=="LSTM":
                    series=lstm_prepare_series(df)
                    result=run_lstm_pipeline(series,horizon)
                else:
                    raise HTTPException(400,"model must be AUTO, ARIMA or LSTM")
            except ValueError as e:
                raise HTTPException(400,str(e))
            except Exception as e:
                raise HTTPException(500,f"Forecast Studio failed: {e}")
        cache_put(cache_id,{"selected_model":selected,"result":result,"comparison":comparison})

    history_start=pd.to_datetime(df["sale_date"]).min()
    history_end=pd.to_datetime(df["sale_date"]).max()
    daily=df.groupby(pd.to_datetime(df["sale_date"]).dt.normalize())["quantity"].sum().sort_index()
    history=[
        {"date":d.strftime("%Y-%m-%d"),"value":float(v)}
        for d,v in daily.tail(180).items()
    ]

    return {
        "product_id":product.id,
        "product":product.name,
        "sku":product.sku,
        "selected_model":selected,
        "selection_mode":model.upper(),
        "history_start":history_start.strftime("%Y-%m-%d"),
        "history_end":history_end.strftime("%Y-%m-%d"),
        "history":history,
        "forecast":result["forecast"],
        "metrics":result["metrics"],
        "model_details": {
            k:v for k,v in result.items()
            if k not in ("forecast","metrics")
        },
        "comparison":comparison
    }

@app.post("/api/v1/forecast")
def forecast(req:ForecastRequest, db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    if req.horizon<1 or req.horizon>365: raise HTTPException(400,"Horizon must be 1-365 days.")
    if not scoped_products(db,user).filter(Product.id==req.product_id).first():
        raise HTTPException(404,"Product not found")
    try: return generate_forecast(db,req.product_id,req.horizon,user["tenant_id"],user["store_id"])
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception: raise HTTPException(500,"Forecast generation could not be completed.")

@app.get("/api/v1/inventory/advisor")
def inventory_advisor(product_id:int, db:Session=Depends(get_db),
                      user=Depends(require_roles("OWNER","MANAGER","STAFF","ANALYST"))):
    p=scoped_products(db,user).filter(Product.id==product_id).first()
    if not p: raise HTTPException(404,"Product not found.")
    return advise(db,p)

@app.get("/api/v1/restock/center")
def restock_center_api(db:Session=Depends(get_db),
                       user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    return restock_center(db,user["tenant_id"],user["store_id"])

@app.get("/api/v1/restock")
def restock(db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","STAFF"))):
    out=[]
    for p in scoped_products(db,user).all():
        try: out.append(restock_for_product(db,p.id,user["tenant_id"],user["store_id"]))
        except Exception: pass
    return out

@app.post("/api/v1/scenarios")
def scenario(req:ScenarioRequest, db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST"))):
    """Run what-if analysis directly from the currently uploaded store dataset.

    Scenario analysis must never depend on a previously generated forecast. It
    uses the latest stored forecast when available and falls back to the
    uploaded sales history, so a newly replaced dataset works immediately.
    """
    if req.horizon < 1 or req.horizon > 365:
        raise HTTPException(400, "Horizon must be 1-365 days.")
    p=scoped_products(db,user).filter(Product.id==req.product_id).first()
    if not p:
        raise HTTPException(404,"Product not found")
    try:
        base = calculate_scenario(
            db, p,
            demand_change_pct=0,
            lead_time_change_days=0,
            safety_stock_change_pct=0,
            horizon=req.horizon
        )
        base_daily=float(base["base_daily_demand"])
        scenario_daily=max(0.0, base_daily*(1+float(req.demand_change_percent)/100.0))
        stock=max(0.0, float(p.current_stock)*(1+float(req.stock_change_percent)/100.0))
        lead=int(req.lead_time_days if req.lead_time_days is not None else p.lead_time_days)
        safety=max(0.0, float(p.safety_stock)*(1+float(req.safety_stock_change_percent)/100.0))
        reorder_point=scenario_daily*max(0,lead)+safety
        target_stock=scenario_daily*(max(0,lead)+req.horizon)+safety
        order=max(0.0,target_stock-stock)
        days_cover=stock/scenario_daily if scenario_daily>0 else None
        risk="HEALTHY" if order<=0 else ("CRITICAL" if stock<=safety or (days_cover is not None and days_cover<=lead) else "ATTENTION")
        return {
            "label":"SIMULATED SCENARIO",
            "data_source":"uploaded_store_dataset",
            "product_id":p.id,
            "product":p.name,
            "sku":p.sku,
            "base_daily_demand":round(base_daily,2),
            "scenario_daily_demand":round(scenario_daily,2),
            "scenario_forecast_demand":round(scenario_daily*req.horizon,2),
            "current_stock":round(float(p.current_stock),2),
            "available_stock":round(stock,2),
            "stock_change_percent":round(float(req.stock_change_percent),2),
            "scenario_lead_time_days":lead,
            "scenario_safety_stock":round(safety,2),
            "reorder_point":round(reorder_point,2),
            "target_stock":round(target_stock,2),
            "recommended_order":round(order,2),
            "days_of_cover":None if days_cover is None else round(days_cover,2),
            "risk":risk,
            "horizon_days":req.horizon,
        }
    except ValueError as e:
        raise HTTPException(400,str(e))
    except Exception as e:
        raise HTTPException(500,f"Scenario calculation failed: {e}")

@app.post("/api/v1/copilot")
def copilot(req:CopilotRequest, db:Session=Depends(get_db), user=Depends(require_roles("OWNER","MANAGER","ANALYST","CUSTOMER"))):
    """Sunny: conversational, dataset-grounded retail assistant.

    The assistant intentionally answers from the active tenant/store dataset.
    It also contains a small project knowledge layer so common questions about
    ARIMA, LSTM, MAPE, inventory and RetailPulse can be answered without an
    external LLM or API key.
    """
    raw_question=req.question.strip()
    q=raw_question.lower()
    if not q:
        raise HTTPException(400,"Please enter a question.")

    # Resolve short follow-up questions using the most recent user message.
    if req.history and len(q.split()) <= 5 and any(x in q for x in ["it", "that", "this", "there", "more", "why", "how about"]):
        prior=[m.content.strip() for m in req.history if m.role == "user" and m.content.strip()]
        if prior and prior[-1].lower() != q:
            q = f"{prior[-1].lower()} {q}"

    simple_mode = bool(req.simple_mode)
    products=scoped_products(db,user).all()
    sales=scoped_sales(db,user).order_by(Sale.sale_date).all()

    # Lightweight conversational context: the frontend can send recent turns.
    if not products:
        return {
            "answer":"I’m Sunny, your RetailPulse AI assistant. Your workspace is connected, but no products are loaded yet. Upload the dataset in Data Intelligence and I’ll use that dataset across forecasting, inventory, scenarios, reports and recommendations.",
            "data":[],
            "sources":["workspace"],
            "action":"Open Data Intelligence and upload your CSV or Excel dataset."
        }

    product_map={p.id:p for p in products}
    total_units=sum(float(x.quantity or 0) for x in sales)
    total_records=len(sales)
    sales_by={}
    product_days={}
    for x in sales:
        qty=float(x.quantity or 0)
        sales_by[x.product_id]=sales_by.get(x.product_id,0)+qty
        product_days.setdefault(x.product_id,set()).add(x.sale_date.date())

    top_sales=sorted(sales_by.items(),key=lambda kv:kv[1],reverse=True)
    date_start=min((x.sale_date for x in sales),default=None)
    date_end=max((x.sale_date for x in sales),default=None)
    daily_units={}
    for x in sales:
        key=x.sale_date.date()
        daily_units[key]=daily_units.get(key,0)+float(x.quantity or 0)

    def response(answer,data=None,sources=None,action=None, simple_answer=None):
        return {
            "assistant":"Sunny",
            "answer": simple_answer if simple_mode and simple_answer else answer,
            "technical_answer": answer if simple_mode and simple_answer else None,
            "data":data if data is not None else [],
            "sources":sources or ["uploaded dataset"],
            "action":action,
            "grounded": True,
            "simple_mode": simple_mode
        }

    # Greetings / identity / help
    if any(q.strip() in {"hi","hello","hey","hii","good morning","good afternoon","good evening"} for q in [q]):
        return response(
            f"Hello! I’m Sunny, your RetailPulse AI assistant. I can work with the current dataset containing {len(products)} products, {total_records:,} sales records and {total_units:,.0f} recorded units. Ask me about demand, forecasts, inventory, restocking, scenarios, anomalies, reports or the project itself.",
            {"products":len(products),"sales_records":total_records,"sales_units":round(total_units,2)},
            ["products","sales"],
            "Try: Which products should I restock?"
        )
    if "who are you" in q or "what are you" in q or "your name" in q:
        return response(
            "I’m Sunny — the conversational AI assistant inside RetailPulse AI. I’m designed to explain the uploaded retail dataset, translate analytics into decisions and guide you through forecasting, inventory and replenishment workflows.",
            [],
            ["RetailPulse project"],
            "Ask: What should I do with this dataset?"
        )
    if "what can you do" in q or q in {"help","help me","what can i ask"}:
        return response(
            "I can answer questions about the active dataset and explain the RetailPulse project. I can summarize sales, find top products, identify stock risk, estimate replenishment, explain ARIMA/LSTM and metrics, interpret scenarios, discuss seasonality/anomalies, explain reports and guide you to the right page.",
            [
                {"topic":"Sales","examples":["What are my top products?","How many units were sold?"]},
                {"topic":"Inventory","examples":["Which products should I restock?","Which items are at risk?"]},
                {"topic":"Forecasting","examples":["How accurate are my forecasts?","Explain ARIMA vs LSTM"]},
                {"topic":"Planning","examples":["Run a demand-up scenario","How much safety stock should I keep?"]},
            ],
            ["RetailPulse capabilities"],
            "Ask a natural-language question; you do not need a command."
        )

    # Project / ML knowledge layer
    knowledge={
        "arima":"ARIMA models time-dependent demand using autoregression, differencing and moving-average error terms. RetailPulse selects a suitable order, validates it chronologically and produces a future demand forecast with confidence intervals.",
        "lstm":"LSTM is a recurrent neural-network architecture designed to learn patterns across sequences. In RetailPulse it is used as a deep-learning forecasting alternative and is compared against ARIMA on chronological validation data.",
        "mape":"MAPE (Mean Absolute Percentage Error) expresses forecast error as a percentage. Lower is better, but it can be unstable when actual demand is zero or very small, so RetailPulse also reports MAE and RMSE.",
        "mae":"MAE (Mean Absolute Error) is the average absolute difference between actual and predicted demand. Lower is better and the value stays in the same unit as the demand data.",
        "rmse":"RMSE (Root Mean Squared Error) penalizes larger forecast errors more strongly than MAE. Lower is better.",
        "time series":"A time series is data ordered by time. RetailPulse converts uploaded sales records into daily demand series before running forecasting and seasonality analysis.",
        "safety stock":"Safety stock is a buffer inventory level intended to protect against demand variability and replenishment uncertainty. RetailPulse uses it when calculating reorder points and recommended order quantities.",
        "lead time":"Lead time is the number of days between placing a replenishment order and receiving it. Higher lead time increases lead-time demand and usually increases the reorder point.",
        "reorder point":"Reorder point is the stock threshold at which replenishment should be triggered. A common structure is lead-time demand plus safety stock.",
        "scenario planner":"Scenario Planner lets you change demand, stock, lead time and safety-stock assumptions and immediately see the impact on reorder point, target stock, days of cover and recommended order quantity.",
        "retailpulse":"RetailPulse AI is an AI-driven retail operating platform that turns an uploaded sales dataset into demand forecasts, inventory intelligence, replenishment recommendations, scenario analysis, reports and conversational decision support.",
        "python":"Python is the main backend/ML language in this project. FastAPI exposes the retail APIs, pandas handles dataset preparation, statsmodels supports ARIMA, and TensorFlow/Keras supports LSTM forecasting.",
        "fastapi":"FastAPI is the Python web framework powering RetailPulse's backend API. The React frontend calls these authenticated endpoints for data, forecasting, inventory, scenarios, reports and Sunny.",
        "postgresql":"PostgreSQL is the persistent source of truth for the active store dataset, including products, sales, forecasts, alerts, users and audit records.",
        "react":"React powers the RetailPulse frontend. The application uses reusable page components, routing, responsive controls and a conversational Sunny interface.",
        "vite":"Vite is the frontend development/build tool. It serves the React application locally and produces the optimized production bundle.",
        "machine learning":"Machine learning lets RetailPulse learn patterns from historical demand and use them for forecasting and decision support.",
        "architecture":"RetailPulse uses a React/Vite frontend, FastAPI backend, PostgreSQL database and forecasting services. Uploaded data flows through validation and cleaning into PostgreSQL, and every downstream operational module reads the same tenant/store-scoped dataset.",
        "python":"Python is a general-purpose programming language known for readable syntax and a large ecosystem. In RetailPulse it powers FastAPI, pandas, statistical forecasting and deep learning.",
        "javascript":"JavaScript is the programming language used by the React frontend. It handles UI state, API calls, routing and interactive components.",
        "sql":"SQL is used to query relational databases. RetailPulse uses PostgreSQL and SQLAlchemy to store and retrieve products, sales, forecasts, inventory and operational data.",
        "api":"An API is an interface that lets software systems communicate. RetailPulse exposes authenticated FastAPI endpoints that the React frontend calls for data and intelligence.",
        "rest api":"A REST API exposes resources through HTTP methods such as GET, POST, PUT and DELETE. RetailPulse uses REST-style endpoints for its application modules.",
        "database":"A database stores structured information so applications can query and update it reliably. RetailPulse uses PostgreSQL as the operational source of truth.",
        "postgres":"PostgreSQL is an open-source relational database. It provides transactions, constraints, indexing and SQL queries for RetailPulse's persistent data.",
        "csv":"CSV stands for comma-separated values. It is a tabular file format that RetailPulse can validate, clean and import into the active store dataset.",
        "excel":"Excel workbooks store tabular business data in spreadsheet sheets. RetailPulse can use spreadsheet-style data when it matches the supported import schema.",
        "machine learning":"Machine learning uses historical examples to learn patterns that can support prediction or classification. RetailPulse applies time-series learning to historical demand.",
        "deep learning":"Deep learning uses neural networks with multiple learned layers. LSTM is the deep-learning forecasting model used in RetailPulse.",
        "neural network":"A neural network is a function approximator built from interconnected weighted units. During training, its weights are optimized to reduce prediction error.",
        "regression":"Regression predicts a numeric value. Demand forecasting is a time-dependent regression-style prediction problem, although dedicated time-series models are better suited to temporal structure.",
        "classification":"Classification predicts a category or class. Inventory risk labels such as HEALTHY, WATCH and CRITICAL are examples of operational classification rules in RetailPulse.",
        "overfitting":"Overfitting happens when a model learns training noise too closely and performs poorly on unseen data. Chronological validation and simpler models help reduce this risk in time-series forecasting.",
        "underfitting":"Underfitting occurs when a model is too simple to capture important patterns in the data. It can cause high error on both training and validation data.",
        "train test split":"For time series, training data should come before validation data chronologically. Random shuffling can leak future information into the past and produce misleading accuracy.",
        "cross validation":"Time-series cross-validation evaluates models across multiple chronological train-validation windows rather than randomly mixing future and past observations.",
        "normalization":"Normalization rescales numeric inputs to a consistent range. It is commonly useful before neural-network training because it can improve optimization stability.",
        "standardization":"Standardization transforms a variable using its mean and standard deviation. It is another common preprocessing step for machine-learning inputs.",
        "gradient descent":"Gradient descent iteratively changes model parameters in the direction that reduces a loss function. Neural networks such as LSTMs are commonly trained with gradient-based optimization.",
        "epoch":"An epoch is one complete pass through the training data during neural-network training. More epochs can improve learning until the model starts overfitting.",
        "batch size":"Batch size is the number of training samples processed before a neural-network weight update. Larger batches can improve throughput but use more memory.",
        "hyperparameter":"A hyperparameter is a setting chosen outside the learned model parameters, such as ARIMA order, learning rate, sequence length or number of LSTM units.",
        "kpi":"A KPI is a key performance indicator used to track business performance. RetailPulse exposes demand, inventory, forecast and replenishment KPIs.",
        "inventory turnover":"Inventory turnover measures how frequently inventory is sold and replenished over a period. Higher turnover can indicate efficient inventory use, but the right level depends on margins and service targets.",
        "supply chain":"A supply chain covers the movement of products, information and replenishment from suppliers through operations to customers. RetailPulse focuses on demand, inventory and replenishment decisions.",
        "safety stock":"Safety stock is a buffer inventory level intended to protect against demand variability and replenishment uncertainty. RetailPulse uses it when calculating reorder points and recommended order quantities.",
        "reorder point":"Reorder point is the stock threshold at which replenishment should be triggered. A common structure is lead-time demand plus safety stock.",
        "json":"JSON is a lightweight data-interchange format made of objects and arrays. RetailPulse's API exchanges request and response data as JSON.",
        "http":"HTTP is the protocol used for web communication. RetailPulse's browser frontend sends HTTP requests to FastAPI endpoints.",
        "authentication":"Authentication verifies who a user is. RetailPulse uses token-based authentication before protected workspace endpoints can be accessed.",
        "authorization":"Authorization determines what an authenticated user is allowed to do. RetailPulse applies role-based permissions such as OWNER, MANAGER, ANALYST and STAFF.",
        "react":"React is a component-based JavaScript UI library. RetailPulse uses React for pages, forms, dashboards, routing and the Sunny conversational interface.",
        "vite":"Vite is a fast frontend development and build tool. It serves RetailPulse during development and creates production assets for deployment.",
        "git":"Git is a version-control system used to track source-code changes. RetailPulse can be committed and pushed to GitHub as a normal software project.",
        "github":"GitHub hosts Git repositories and supports collaboration, issues, pull requests and CI/CD workflows. RetailPulse can be maintained as a GitHub repository.",
        "docker":"Docker packages an application and its dependencies into containers. RetailPulse includes Docker configuration for repeatable local or deployment environments.",
        "fastapi":"FastAPI is the Python web framework powering RetailPulse's backend API. The React frontend calls these authenticated endpoints for data, forecasting, inventory, scenarios, reports and Sunny.",
        "pandas":"pandas is a Python data-analysis library built around DataFrame structures. RetailPulse uses it for dataset validation, aggregation and time-series preparation.",
        "tensorflow":"TensorFlow is a machine-learning framework used for neural networks. RetailPulse uses TensorFlow/Keras for its LSTM forecasting implementation.",
        "statsmodels":"statsmodels is a Python statistical-modeling library. RetailPulse uses it for ARIMA time-series forecasting.",
        "llm":"An LLM is a large language model trained to understand and generate natural language. Sunny is implemented as a lightweight project-grounded assistant in this version, with deterministic project knowledge and live dataset context rather than pretending to be an external LLM.",
        "prompt engineering":"Prompt engineering is the practice of structuring instructions and context to improve language-model responses. It becomes especially useful when connecting Sunny to an external LLM provider.",
        "generative ai":"Generative AI creates text, code, images or other content from learned patterns. A future LLM-backed Sunny deployment could use generative AI while keeping RetailPulse data grounding and access controls.",
        "ai":"Artificial intelligence is the broader field of building systems that perform tasks associated with human intelligence. RetailPulse combines predictive analytics, time-series models and conversational decision support.",
        "data science":"Data science combines statistics, programming, data engineering and domain knowledge to extract useful insights. RetailPulse applies these disciplines to retail demand and inventory.",
        "time series":"A time series is data ordered by time. RetailPulse converts uploaded sales records into daily demand series before running forecasting and seasonality analysis."
    }
    if "arima" in q and "lstm" in q:
        return response(
            "ARIMA and LSTM solve the same forecasting goal from different modeling perspectives. ARIMA is statistical, transparent and strong for structured temporal patterns; LSTM is a neural sequence model that can learn more complex nonlinear relationships but needs more training data and compute. RetailPulse compares them with chronological validation using MAE, RMSE and MAPE, then can select the stronger model for a product.",
            [{"model":"ARIMA","type":"statistical","strength":"transparent, fast, strong baseline"},
             {"model":"LSTM","type":"deep learning","strength":"sequence learning, nonlinear patterns"}],
            ["RetailPulse forecasting engine"],
            "Open Model Evaluation to compare both on the active dataset."
        )
    for term,answer in knowledge.items():
        if term in q:
            return response(answer,[],["RetailPulse project knowledge"],"Ask me how this concept applies to your current dataset.")

    # Dataset / data quality
    if any(w in q for w in ["dataset","data loaded","data source","how many products","how many sales","records","date range","uploaded"]):
        date_text=f"{date_start:%Y-%m-%d} to {date_end:%Y-%m-%d}" if date_start and date_end else "no dates available"
        return response(
            f"The active store dataset contains {len(products):,} products and {total_records:,} sales records, representing {total_units:,.0f} recorded units across {date_text}. All operational pages are scoped to this store dataset.",
            {"products":len(products),"sales_records":total_records,"sales_units":round(total_units,2),"date_start":date_start.strftime("%Y-%m-%d") if date_start else None,"date_end":date_end.strftime("%Y-%m-%d") if date_end else None},
            ["products","sales"],
            "Open Data Intelligence to inspect data quality and forecast readiness."
        )

    # Precise data questions are checked before broad keyword intents.
    product_match=None
    for p in products:
        pname=p.name.lower()
        if pname in q or str(p.sku).lower() in q:
            product_match=p
            break

    if product_match and any(w in q for w in ["how many", "how much", "sold", "sales", "units"]):
        p=product_match
        sold=sales_by.get(p.id,0)
        days=len(product_days.get(p.id,set()))
        daily=sold/max(days,1)
        return response(
            f"{p.name} sold {sold:,.0f} units in the uploaded sales history. That is about {daily:,.2f} units per active sales day.",
            [{"product":p.name,"units_sold":round(sold,2),"active_sales_days":days,"average_units_per_active_day":round(daily,2)}],
            ["sales","products"], None,
            f"{p.name} sold {sold:,.0f} units. That means about {daily:,.2f} units on a day when sales were recorded."
        )

    if product_match and any(w in q for w in ["stock", "inventory", "available", "cover", "run out"]):
        p=product_match
        daily=sales_by.get(p.id,0)/max(len(product_days.get(p.id,set())),1)
        cover=p.current_stock/daily if daily>0 else None
        simple=(f"{p.name} has {p.current_stock:,.0f} units. At its recorded daily demand, that is about {cover:,.1f} days of stock."
                if cover is not None else
                f"{p.name} has {p.current_stock:,.0f} units in stock. There is not enough recorded demand to estimate when it will run out.")
        technical=(f"{p.name} currently has {p.current_stock:,.0f} units in stock against {p.safety_stock:,.0f} units of safety stock. "
                    f"Its recorded demand averages {daily:,.2f} units per active sales day, giving about {cover:,.1f} days of cover."
                    if cover is not None else
                    f"{p.name} has {p.current_stock:,.0f} units in stock against {p.safety_stock:,.0f} units of safety stock, but there is not enough demand history to estimate days of cover.")
        return response(
            technical,
            [{"product":p.name,"stock":round(p.current_stock,2),"safety_stock":round(p.safety_stock,2),
              "daily_demand":round(daily,2),"days_cover":None if cover is None else round(cover,2)}],
            ["products","sales","inventory"], None, simple
        )

    if any(w in q for w in ["total sales", "total units", "how many units", "how much did we sell", "how much have we sold"]):
        return response(
            f"The uploaded dataset contains {total_units:,.0f} recorded sales units across {total_records:,} sales records.",
            [{"sales_units":round(total_units,2),"sales_records":total_records}],
            ["sales"], None,
            f"You sold {total_units:,.0f} units in the uploaded data, across {total_records:,} sales records."
        )

    # Product-specific questions
    product_match=None
    for p in products:
        pname=p.name.lower()
        if pname in q or str(p.sku).lower() in q:
            product_match=p
            break
    if product_match and any(w in q for w in ["stock","inventory","available","cover","restock","order","risk"]):
        p=product_match
        daily=sales_by.get(p.id,0)/max(len(product_days.get(p.id,set())),1)
        cover=p.current_stock/daily if daily>0 else None
        need=max(0,daily*(p.lead_time_days+30)+p.safety_stock-p.current_stock)
        risk="CRITICAL" if p.current_stock<=p.safety_stock else ("WATCH" if cover is not None and cover<=p.lead_time_days else "HEALTHY")
        return response(
            f"{p.name} currently has {p.current_stock:,.0f} units in stock against {p.safety_stock:,.0f} units of safety stock. Its recorded demand averages about {daily:,.2f} units per active sales day, giving roughly {cover:,.1f} days of cover when demand is available. I classify the current position as {risk}.",
            [{"product":p.name,"sku":p.sku,"stock":round(p.current_stock,2),"safety_stock":round(p.safety_stock,2),"daily_demand":round(daily,2),"days_cover":None if cover is None else round(cover,2),"estimated_order":round(need,2),"risk":risk}],
            ["products","sales","inventory"],
            "Open Restock Center to review the replenishment recommendation."
        )

    # Restocking
    if any(w in q for w in ["restock","reorder","replenish","run out","order stock","buy stock"]):
        ranked=[]
        for p in products:
            days=len(product_days.get(p.id,set()))
            daily=sales_by.get(p.id,0)/max(days,1)
            cover=p.current_stock/daily if daily>0 else None
            need=max(0,daily*(p.lead_time_days+30)+p.safety_stock-p.current_stock)
            risk="CRITICAL" if p.current_stock<=p.safety_stock else ("WATCH" if cover is not None and cover<=p.lead_time_days else "HEALTHY")
            ranked.append({"product":p.name,"sku":p.sku,"current_stock":round(p.current_stock,2),"daily_demand":round(daily,2),"recommended_order":round(need,2),"days_cover":None if cover is None else round(cover,2),"risk":risk})
        ranked.sort(key=lambda x:(x["recommended_order"],x["risk"]=="CRITICAL"),reverse=True)
        return response(
            "Based on the uploaded sales history, current stock, lead time and safety stock, these products have the highest replenishment need.",
            ranked[:10],
            ["products","sales","inventory"],
            "Open Restock Center to review and act on these recommendations."
        )

    # Risk
    if any(w in q for w in ["risk","critical","low stock","danger","at risk"]):
        risks=[]
        for p in products:
            daily=sales_by.get(p.id,0)/max(len(product_days.get(p.id,set())),1)
            cover=p.current_stock/daily if daily>0 else None
            risk="CRITICAL" if p.current_stock<=p.safety_stock else ("WATCH" if cover is not None and cover<=p.lead_time_days else "HEALTHY")
            risks.append({"product":p.name,"stock":round(p.current_stock,2),"safety_stock":round(p.safety_stock,2),"days_cover":None if cover is None else round(cover,2),"risk":risk})
        risks.sort(key=lambda x:({"CRITICAL":0,"WATCH":1,"HEALTHY":2}[x["risk"]],x["days_cover"] if x["days_cover"] is not None else 999))
        return response("Here is the current inventory risk ranking from the uploaded dataset.",risks[:10],["products","sales","inventory"],"Open Action Center for operational alerts.")

    # Top products / demand
    if any(w in q for w in ["top","best selling","best-selling","highest sales","most sold","demand"]):
        data=[{"rank":i+1,"product":product_map[pid].name,"units":round(v,2)} for i,(pid,v) in enumerate(top_sales[:10]) if pid in product_map]
        return response(f"The top product by recorded sales is {data[0]['product']} with {data[0]['units']:,.0f} units." if data else "There are no sales records to rank yet.",data,["sales","products"],"Open Reports & Analytics for the full demand trend.")

    # Forecasts
    if any(w in q for w in ["forecast","forecasting","accuracy","mape","model evaluation"]):
        latest={}
        for f in db.query(Forecast).filter(Forecast.tenant_id==user["tenant_id"],Forecast.store_id==user["store_id"]).order_by(Forecast.created_at.desc()).all():
            latest.setdefault(f.product_id,f)
        if not latest:
            return response("There are no stored forecasts yet. The uploaded sales data is available, but a model needs to be run for a product before forecast results can be quoted.",[],["sales","forecasts"],"Open ARIMA Lab or LSTM Lab and generate a forecast.")
        rows=[]
        for pid,f in latest.items():
            vals=db.query(ForecastValue).filter(ForecastValue.forecast_id==f.id).all()
            rows.append({"product":product_map[pid].name if pid in product_map else str(pid),"model":f.model,"mape":None if f.mape is None else round(float(f.mape),2),"forecast_units":round(sum(max(0,float(v.value or 0)) for v in vals),2)})
        rows.sort(key=lambda x:x["forecast_units"],reverse=True)
        return response(f"I found {len(rows)} stored forecasts for the current dataset. The highest projected demand is {rows[0]['product']} using {rows[0]['model']}.",rows[:10],["forecasts","forecast_values"],"Open Model Evaluation to compare ARIMA and LSTM.")

    # Sales / report questions
    if any(w in q for w in ["sales","sold","units","revenue"]):
        data=[{"date":str(k),"units":round(v,2)} for k,v in sorted(daily_units.items())[-30:]]
        return response(f"The active dataset contains {total_units:,.0f} recorded sales units across {total_records:,} sales records. The last 30 available dates are summarized below.",data,["sales"],"Open Reports & Analytics for daily, weekly, monthly and yearly views.")

    # Dataset-driven project operations
    if any(w in q for w in ["seasonality","anomal","pattern"]):
        return response("RetailPulse can analyze weekly demand patterns and anomalies for any uploaded product with sufficient history. Choose a product in Seasonality & Anomalies to run the analysis on this dataset.",[],["sales","seasonality engine"],"Open Seasonality & Anomalies.")

    if any(w in q for w in ["scenario","what if","what-if"]):
        return response("Scenario Planner is connected to the active uploaded dataset. It can vary demand, stock, lead time and safety stock and calculate the resulting reorder point, target stock, days of cover and recommended order.",[],["products","sales","scenario engine"],"Open Scenario Planner.")

    if any(w in q for w in ["report","analytics","trend","growth"]):
        return response("Reports & Analytics aggregates the active uploaded sales records into daily, weekly, monthly and yearly views, with KPIs, demand trends and top products.",[],["sales","reports engine"],"Open Reports & Analytics.")

    if any(w in q for w in ["upload","import","csv","excel","file"]):
        return response("Upload your CSV/XLSX in Data Intelligence. For the workspace owner, Upload & Replace validates and cleans the file, replaces the current store products/sales/forecasts/alerts, and verifies the resulting PostgreSQL counts. Every operational page then reads from that active store dataset.",[],["data pipeline"],"Open Data Intelligence.")

    # Follow-up/contextual questions
    if any(w in q for w in ["why","explain","how","should i","what should i do","next"]):
        return response(
            "For this RetailPulse workspace, the safest workflow is: validate the uploaded dataset, inspect Data Intelligence quality/readiness, generate a forecast for a representative product, review inventory risk and Restock Center recommendations, then use Scenario Planner to test demand/lead-time assumptions. I can walk through any of those steps.",
            [],
            ["RetailPulse workflow"],
            "Tell me which step you want to explore."
        )

    # Broad conversational fallback: answer common general-knowledge questions without inventing dataset facts.
    general_topics={
        "algorithm":"An algorithm is a finite sequence of steps for solving a problem or transforming input into output. Good algorithms balance correctness, efficiency and clarity.",
        "data structure":"A data structure organizes data for efficient access and modification. Common examples include arrays, linked lists, stacks, queues, hash tables, trees and graphs.",
        "oop":"Object-oriented programming organizes software around objects containing state and behavior. Core ideas include encapsulation, inheritance, abstraction and polymorphism.",
        "operating system":"An operating system manages hardware and provides services for applications. Examples include Windows, Linux and macOS.",
        "computer network":"A computer network connects devices so they can exchange data. Important concepts include IP addressing, routing, TCP/UDP, DNS and HTTP.",
        "cloud computing":"Cloud computing provides compute, storage, databases and other services over networks. It can improve scalability and reduce the need to manage physical infrastructure directly.",
        "cybersecurity":"Cybersecurity protects systems and data from unauthorized access, disruption and abuse. Strong authentication, least privilege, encryption, patching and monitoring are foundational practices.",
        "statistics":"Statistics is the study of collecting, summarizing, analyzing and interpreting data. Mean, median, variance, confidence intervals and hypothesis tests are common statistical tools.",
        "probability":"Probability quantifies uncertainty. It ranges from 0 to 1 and is used in statistics, machine learning, risk analysis and decision-making.",
        "linear regression":"Linear regression models a numeric outcome as a linear function of input variables. It is simple, interpretable and often useful as a baseline.",
        "decision tree":"A decision tree predicts an outcome by recursively splitting data using feature-based rules. It is interpretable and can support both classification and regression.",
        "random forest":"Random forest combines many decision trees and aggregates their predictions. The ensemble often improves robustness compared with a single tree.",
        "sql injection":"SQL injection is a security vulnerability where untrusted input changes the meaning of a database query. Parameterized queries and ORM query binding are standard defenses.",
        "rest api":"A REST API exposes resources through HTTP endpoints and commonly uses JSON for data exchange. GET usually retrieves data while POST creates or triggers an operation.",
        "frontend":"A frontend is the part of an application users interact with in a browser or app. RetailPulse's frontend is built with React and Vite.",
        "backend":"A backend handles business logic, data access and APIs behind the user interface. RetailPulse's backend uses Python and FastAPI.",
        "full stack":"Full-stack development covers both frontend and backend concerns, plus databases, APIs, authentication and deployment.",
    }
    for term,answer in general_topics.items():
        if term in q:
            return response(answer,[],["Sunny general knowledge"],"Ask me to connect this concept to RetailPulse if you want a project-specific explanation.")

    return response(
        f"I can help with that in the context of RetailPulse. I currently have {len(products):,} products and {total_records:,} sales records from the active dataset. I can explain the project, analyze your data, or guide you through forecasting, inventory, scenarios, reports and Sunny itself. If your question is outside the retail project, give me the context and I’ll do my best to answer without inventing store facts.",
        [],
        ["uploaded dataset","RetailPulse project knowledge"],
        "Try asking in plain language, for example: “What is driving demand?” or “Explain ARIMA vs LSTM.”"
    )

