
from __future__ import annotations
from datetime import datetime, timedelta
import statistics
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import Product, Sale, Forecast, ForecastValue

def scoped_product(db, product_id, tenant_id, store_id):
    return db.query(Product).filter(
        Product.id==product_id,
        Product.tenant_id==tenant_id,
        Product.store_id==store_id
    ).first()

def sales_summary(db: Session, product_id, tenant_id, store_id, days=30):
    start=datetime.utcnow()-timedelta(days=days)
    rows=db.query(Sale).filter(
        Sale.product_id==product_id,
        Sale.tenant_id==tenant_id,
        Sale.store_id==store_id,
        Sale.sale_date>=start
    ).order_by(Sale.sale_date).all()
    units=sum(float(r.quantity) for r in rows)
    active_days=len({r.sale_date.date() for r in rows})
    avg=units/max(active_days,1)
    return {
        "period_days":days,
        "units_sold":round(units,2),
        "active_days":active_days,
        "average_daily_demand":round(avg,2),
        "transactions":len(rows)
    }

def inventory_position(db, product_id, tenant_id, store_id):
    p=scoped_product(db,product_id,tenant_id,store_id)
    if not p: return None
    latest=db.query(Forecast).filter(
        Forecast.product_id==product_id,
        Forecast.tenant_id==tenant_id,
        Forecast.store_id==store_id
    ).order_by(Forecast.created_at.desc()).first()
    forecast_total=0.0
    forecast_daily=0.0
    if latest:
        vals=db.query(ForecastValue).filter(ForecastValue.forecast_id==latest.id).all()
        forecast_total=sum(v.value for v in vals)
        forecast_daily=forecast_total/max(len(vals),1)

    summary=sales_summary(db,product_id,tenant_id,store_id,30)
    daily=max(forecast_daily,summary["average_daily_demand"],0)
    lead_demand=daily*p.lead_time_days
    reorder_point=lead_demand+p.safety_stock
    available=p.current_stock
    days_cover=(available/daily) if daily>0 else 999
    gap=max(0,reorder_point-available)

    if available<=p.safety_stock or days_cover<=max(1,p.lead_time_days):
        risk="CRITICAL"
    elif gap>0 or days_cover<=p.lead_time_days*1.5:
        risk="ATTENTION"
    else:
        risk="HEALTHY"

    return {
        "product_id":p.id,"sku":p.sku,"product":p.name,"category":p.category,
        "current_stock":round(p.current_stock,2),
        "safety_stock":round(p.safety_stock,2),
        "lead_time_days":p.lead_time_days,
        "average_daily_demand":round(daily,2),
        "lead_time_demand":round(lead_demand,2),
        "reorder_point":round(reorder_point,2),
        "days_of_cover":round(days_cover,2) if days_cover<999 else None,
        "stock_gap":round(gap,2),
        "inventory_risk":risk,
        "latest_forecast_id":latest.id if latest else None,
        "latest_model":latest.model if latest else None,
        "latest_mape":latest.mape if latest else None,
        "last_30_days":summary
    }

def inventory_dashboard(db,tenant_id,store_id):
    products=db.query(Product).filter(Product.tenant_id==tenant_id,Product.store_id==store_id).all()
    rows=[inventory_position(db,p.id,tenant_id,store_id) for p in products]
    rows=[r for r in rows if r]
    total_stock=sum(r["current_stock"] for r in rows)
    critical=sum(r["inventory_risk"]=="CRITICAL" for r in rows)
    attention=sum(r["inventory_risk"]=="ATTENTION" for r in rows)
    healthy=sum(r["inventory_risk"]=="HEALTHY" for r in rows)
    return {
        "total_products":len(rows),
        "total_stock_units":round(total_stock,2),
        "critical":critical,"attention":attention,"healthy":healthy,
        "health_score":round((healthy/max(len(rows),1))*100,1),
        "items":sorted(rows,key=lambda x:({"CRITICAL":0,"ATTENTION":1,"HEALTHY":2}[x["inventory_risk"]],-x["stock_gap"]))
    }

def update_stock(db, product_id, tenant_id, store_id, new_stock):
    p=scoped_product(db,product_id,tenant_id,store_id)
    if not p: return None
    if new_stock<0: raise ValueError("Stock cannot be negative.")
    p.current_stock=float(new_stock)
    db.commit()
    return inventory_position(db,product_id,tenant_id,store_id)
