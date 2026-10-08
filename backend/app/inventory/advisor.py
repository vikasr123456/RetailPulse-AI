
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import Product, Sale, Forecast, ForecastValue

def product_rows(db, tenant_id, store_id):
    return db.query(Product).filter(
        Product.tenant_id==tenant_id,
        Product.store_id==store_id
    ).all()

def demand_rate(db:Session, product:Product, days=30):
    start=datetime.utcnow()-timedelta(days=days)
    rows=db.query(Sale).filter(
        Sale.product_id==product.id,
        Sale.tenant_id==product.tenant_id,
        Sale.store_id==product.store_id,
        Sale.sale_date>=start
    ).all()
    total=sum(float(x.quantity) for x in rows)
    active=len({x.sale_date.date() for x in rows})
    return total/max(active,1)

def latest_forecast(db,product):
    f=db.query(Forecast).filter(
        Forecast.product_id==product.id,
        Forecast.tenant_id==product.tenant_id,
        Forecast.store_id==product.store_id
    ).order_by(Forecast.created_at.desc()).first()
    if not f:return None
    vals=db.query(ForecastValue).filter(ForecastValue.forecast_id==f.id).order_by(ForecastValue.forecast_date).all()
    return f,vals

def advise(db:Session,product:Product,horizon=30):
    daily=demand_rate(db,product,30)
    latest=latest_forecast(db,product)
    model_daily=daily
    forecast_total=None
    mape=None
    model=None

    if latest:
        f,vals=latest
        if vals:
            forecast_total=sum(max(0,float(v.value)) for v in vals[:horizon])
            model_daily=forecast_total/max(min(horizon,len(vals)),1)
        mape=f.mape
        model=f.model

    # Conservative business rule: use the higher of recent demand and model demand.
    planning_daily=max(daily,model_daily,0)
    lead_demand=planning_daily*max(product.lead_time_days,0)
    reorder_point=lead_demand+max(product.safety_stock,0)
    target_stock=planning_daily*(max(product.lead_time_days,0)+30)+max(product.safety_stock,0)
    order_qty=max(0,target_stock-product.current_stock)

    cover=(product.current_stock/planning_daily) if planning_daily>0 else None
    if order_qty<=0:
        status="HEALTHY"
    elif product.current_stock<=product.safety_stock or (cover is not None and cover<=product.lead_time_days):
        status="CRITICAL"
    else:
        status="ATTENTION"

    if status=="CRITICAL":
        priority="URGENT"
    elif status=="ATTENTION":
        priority="HIGH"
    else:
        priority="NORMAL"

    return {
        "product_id":product.id,
        "sku":product.sku,
        "product":product.name,
        "category":product.category,
        "current_stock":round(product.current_stock,2),
        "recent_daily_demand":round(daily,2),
        "planning_daily_demand":round(planning_daily,2),
        "forecast_demand":round(forecast_total,2) if forecast_total is not None else None,
        "lead_time_days":product.lead_time_days,
        "safety_stock":round(product.safety_stock,2),
        "lead_time_demand":round(lead_demand,2),
        "reorder_point":round(reorder_point,2),
        "target_stock":round(target_stock,2),
        "recommended_order":round(order_qty,2),
        "days_of_cover":round(cover,2) if cover is not None else None,
        "status":status,
        "priority":priority,
        "model":model,
        "mape":round(mape,2) if mape is not None else None,
        "reason":(
            "Order recommended to cover lead time, safety stock and the next 30 days of planned demand."
            if order_qty>0 else
            "Current stock is sufficient under the current planning assumptions."
        )
    }

def restock_center(db,tenant_id,store_id):
    rows=[advise(db,p) for p in product_rows(db,tenant_id,store_id)]
    rows.sort(key=lambda x:(
        {"URGENT":0,"HIGH":1,"NORMAL":2}[x["priority"]],
        -x["recommended_order"]
    ))
    return {
        "items":rows,
        "urgent":sum(x["priority"]=="URGENT" for x in rows),
        "high":sum(x["priority"]=="HIGH" for x in rows),
        "normal":sum(x["priority"]=="NORMAL" for x in rows),
        "recommended_units":round(sum(x["recommended_order"] for x in rows),2),
        "products_needing_order":sum(x["recommended_order"]>0 for x in rows)
    }
