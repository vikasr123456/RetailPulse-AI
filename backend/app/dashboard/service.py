
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import Product, Sale, Forecast, ForecastValue

def dashboard_data(db: Session, tenant_id: int, store_id: int):
    products=db.query(Product).filter(
        Product.tenant_id==tenant_id,
        Product.store_id==store_id
    ).all()

    now=datetime.utcnow()
    start=now-timedelta(days=30)
    prev_start=now-timedelta(days=60)

    current_rows=db.query(Sale).filter(
        Sale.tenant_id==tenant_id,
        Sale.store_id==store_id,
        Sale.sale_date>=start
    ).all()

    previous_rows=db.query(Sale).filter(
        Sale.tenant_id==tenant_id,
        Sale.store_id==store_id,
        Sale.sale_date>=prev_start,
        Sale.sale_date<start
    ).all()

    current_units=sum(float(x.quantity) for x in current_rows)
    previous_units=sum(float(x.quantity) for x in previous_rows)

    current_active=len({x.sale_date.date() for x in current_rows})
    previous_active=len({x.sale_date.date() for x in previous_rows})

    current_daily=current_units/max(current_active,1)
    previous_daily=previous_units/max(previous_active,1)

    growth=((current_daily-previous_daily)/previous_daily*100) if previous_daily else None

    total_stock=sum(float(p.current_stock) for p in products)
    low_stock=sum(
        1 for p in products
        if p.current_stock <= p.safety_stock
    )

    forecasts=db.query(Forecast).filter(
        Forecast.tenant_id==tenant_id,
        Forecast.store_id==store_id
    ).order_by(Forecast.created_at.desc()).all()

    latest_by_product={}
    for f in forecasts:
        latest_by_product.setdefault(f.product_id,f)

    forecast_rows=[]
    forecast_total=0
    for product_id,f in latest_by_product.items():
        vals=db.query(ForecastValue).filter(
            ForecastValue.forecast_id==f.id
        ).all()
        total=sum(max(0,float(v.value)) for v in vals)
        forecast_total+=total
        forecast_rows.append({
            "product_id":product_id,
            "model":f.model,
            "mape":f.mape,
            "forecast_total":round(total,2)
        })

    accuracy_values=[float(x["mape"]) for x in forecast_rows if x["mape"] is not None]
    avg_mape=sum(accuracy_values)/len(accuracy_values) if accuracy_values else None

    top_products={}
    for row in current_rows:
        top_products[row.product_id]=top_products.get(row.product_id,0)+float(row.quantity)

    product_map={p.id:p for p in products}
    top=sorted(
        [
            {
                "product_id":pid,
                "product":product_map[pid].name,
                "sku":product_map[pid].sku,
                "units":round(units,2)
            }
            for pid,units in top_products.items()
            if pid in product_map
        ],
        key=lambda x:x["units"],
        reverse=True
    )[:10]

    trend=[]
    for i in range(29,-1,-1):
        day=(now-timedelta(days=i)).date()
        units=sum(
            float(x.quantity)
            for x in current_rows
            if x.sale_date.date()==day
        )
        trend.append({
            "date":day.isoformat(),
            "units":round(units,2)
        })

    return {
        "kpis":{
            "products":len(products),
            "sales_units_30d":round(current_units,2),
            "daily_demand_30d":round(current_daily,2),
            "demand_growth_pct":round(growth,2) if growth is not None else None,
            "stock_units":round(total_stock,2),
            "low_stock_products":low_stock,
            "forecast_demand":round(forecast_total,2),
            "average_forecast_mape":round(avg_mape,2) if avg_mape is not None else None
        },
        "trend":trend,
        "top_products":top,
        "forecast_summary":forecast_rows[:10]
    }
