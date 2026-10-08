
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import Product, Sale, Forecast, ForecastValue
from ..dashboard.service import dashboard_data
from ..inventory.advisor import restock_center
from ..alerts.service import build_alerts


def report_summary(db: Session, tenant_id: int, store_id: int, days: int = 30):
    if days not in (7, 30, 60, 90, 365):
        raise ValueError("days must be one of 7, 30, 60, 90 or 365")

    dashboard = dashboard_data(db, tenant_id, store_id)
    restock = restock_center(db, tenant_id, store_id)
    alerts = build_alerts(db, tenant_id, store_id)

    start = datetime.utcnow() - timedelta(days=days)
    sales = db.query(Sale).filter(
        Sale.tenant_id == tenant_id,
        Sale.store_id == store_id,
        Sale.sale_date >= start
    ).all()

    units = sum(float(x.quantity) for x in sales)

    products = db.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.store_id == store_id
    ).all()

    product_map = {p.id: p for p in products}
    by_product = {}
    for row in sales:
        by_product[row.product_id] = by_product.get(row.product_id, 0.0) + float(row.quantity)

    sales_table = sorted(
        [
            {
                "product_id": pid,
                "product": product_map[pid].name,
                "sku": product_map[pid].sku,
                "units": round(qty, 2)
            }
            for pid, qty in by_product.items()
            if pid in product_map
        ],
        key=lambda x: x["units"],
        reverse=True
    )

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "period_days": days,
        "summary": {
            "sales_units": round(units, 2),
            "products": len(products),
            "stock_units": dashboard["kpis"]["stock_units"],
            "forecast_demand": dashboard["kpis"]["forecast_demand"],
            "low_stock_products": dashboard["kpis"]["low_stock_products"],
            "alert_count": alerts["total"],
            "critical_alerts": alerts["critical"],
            "recommended_restock_units": restock["recommended_units"]
        },
        "sales_by_product": sales_table[:50],
        "restock": restock,
        "alerts": alerts,
        "dashboard": dashboard
    }
