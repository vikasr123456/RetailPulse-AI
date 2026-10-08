
from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from ..models import Product

SEVERITY_ORDER={"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}

def build_alerts(db: Session, tenant_id:int, store_id:int):
    products=db.query(Product).filter(
        Product.tenant_id==tenant_id,
        Product.store_id==store_id
    ).all()

    alerts=[]
    for p in products:
        if p.current_stock <= p.safety_stock:
            alerts.append({
                "type":"LOW_STOCK",
                "severity":"CRITICAL",
                "title":f"Critical stock: {p.name}",
                "message":f"Current stock ({p.current_stock:g}) is at or below safety stock ({p.safety_stock:g}).",
                "product_id":p.id,
                "sku":p.sku,
                "created_at":datetime.utcnow().isoformat()
            })
        elif p.current_stock <= p.safety_stock*1.5:
            alerts.append({
                "type":"LOW_STOCK",
                "severity":"HIGH",
                "title":f"Stock attention: {p.name}",
                "message":f"Current stock ({p.current_stock:g}) is approaching safety stock ({p.safety_stock:g}).",
                "product_id":p.id,
                "sku":p.sku,
                "created_at":datetime.utcnow().isoformat()
            })

        if p.lead_time_days >= 30:
            alerts.append({
                "type":"LEAD_TIME",
                "severity":"MEDIUM",
                "title":f"Long lead time: {p.name}",
                "message":f"Configured lead time is {p.lead_time_days} days.",
                "product_id":p.id,
                "sku":p.sku,
                "created_at":datetime.utcnow().isoformat()
            })

    alerts.sort(key=lambda x:SEVERITY_ORDER.get(x["severity"],9))
    return {
        "alerts":alerts,
        "critical":sum(a["severity"]=="CRITICAL" for a in alerts),
        "high":sum(a["severity"]=="HIGH" for a in alerts),
        "medium":sum(a["severity"]=="MEDIUM" for a in alerts),
        "total":len(alerts)
    }
