
from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import Product, Sale, Forecast, ForecastValue


def get_product(db: Session, product_id: int, tenant_id: int, store_id: int):
    return db.query(Product).filter(
        Product.id == product_id,
        Product.tenant_id == tenant_id,
        Product.store_id == store_id
    ).first()


def recent_daily_demand(db: Session, product: Product, days: int = 30) -> float:
    """Use the latest 30 days inside the uploaded dataset, not today's clock.

    Historical retail datasets often end months/years before the current date.
    Anchoring the window to the dataset's latest observation keeps Scenario
    Planner useful immediately after a dataset replacement.
    """
    latest = db.query(Sale.sale_date).filter(
        Sale.product_id == product.id,
        Sale.tenant_id == product.tenant_id,
        Sale.store_id == product.store_id
    ).order_by(Sale.sale_date.desc()).first()
    if not latest:
        return 0.0
    anchor = latest[0]
    start = anchor - timedelta(days=max(days - 1, 0))
    rows = db.query(Sale).filter(
        Sale.product_id == product.id,
        Sale.tenant_id == product.tenant_id,
        Sale.store_id == product.store_id,
        Sale.sale_date >= start,
        Sale.sale_date <= anchor
    ).all()
    total = sum(float(x.quantity) for x in rows)
    active_days = len({x.sale_date.date() for x in rows})
    return total / max(active_days, 1)


def latest_forecast_daily(db: Session, product: Product, horizon: int = 30):
    forecast = db.query(Forecast).filter(
        Forecast.product_id == product.id,
        Forecast.tenant_id == product.tenant_id,
        Forecast.store_id == product.store_id
    ).order_by(Forecast.created_at.desc()).first()

    if not forecast:
        return None

    values = db.query(ForecastValue).filter(
        ForecastValue.forecast_id == forecast.id
    ).order_by(ForecastValue.forecast_date).limit(horizon).all()

    if not values:
        return None

    total = sum(max(0.0, float(v.value)) for v in values)
    return total / len(values)


def calculate_scenario(
    db: Session,
    product: Product,
    demand_change_pct: float = 0.0,
    lead_time_change_days: int = 0,
    safety_stock_change_pct: float = 0.0,
    horizon: int = 30
):
    if horizon < 1 or horizon > 365:
        raise ValueError("Horizon must be 1-365 days.")
    if demand_change_pct < -90:
        raise ValueError("Demand change cannot be below -90%.")
    if safety_stock_change_pct < -100:
        raise ValueError("Safety-stock change cannot be below -100%.")

    recent = recent_daily_demand(db, product, 30)
    forecast_daily = latest_forecast_daily(db, product, horizon)
    base_daily = max(recent, forecast_daily or 0.0)

    scenario_daily = max(0.0, base_daily * (1 + demand_change_pct / 100.0))
    lead_time = max(0, product.lead_time_days + lead_time_change_days)
    safety_stock = max(
        0.0,
        product.safety_stock * (1 + safety_stock_change_pct / 100.0)
    )

    horizon_demand = scenario_daily * horizon
    lead_time_demand = scenario_daily * lead_time
    reorder_point = lead_time_demand + safety_stock
    target_stock = scenario_daily * (lead_time + horizon) + safety_stock
    recommended_order = max(0.0, target_stock - product.current_stock)
    days_cover = (
        product.current_stock / scenario_daily
        if scenario_daily > 0 else None
    )

    if recommended_order <= 0:
        risk = "HEALTHY"
    elif product.current_stock <= safety_stock or (
        days_cover is not None and days_cover <= lead_time
    ):
        risk = "CRITICAL"
    else:
        risk = "ATTENTION"

    return {
        "product_id": product.id,
        "product": product.name,
        "sku": product.sku,
        "base_daily_demand": round(base_daily, 2),
        "scenario_daily_demand": round(scenario_daily, 2),
        "demand_change_pct": round(demand_change_pct, 2),
        "horizon_days": horizon,
        "horizon_demand": round(horizon_demand, 2),
        "base_lead_time_days": product.lead_time_days,
        "scenario_lead_time_days": lead_time,
        "lead_time_change_days": lead_time_change_days,
        "base_safety_stock": round(product.safety_stock, 2),
        "scenario_safety_stock": round(safety_stock, 2),
        "safety_stock_change_pct": round(safety_stock_change_pct, 2),
        "current_stock": round(product.current_stock, 2),
        "lead_time_demand": round(lead_time_demand, 2),
        "reorder_point": round(reorder_point, 2),
        "target_stock": round(target_stock, 2),
        "recommended_order": round(recommended_order, 2),
        "days_of_cover": round(days_cover, 2) if days_cover is not None else None,
        "risk": risk
    }


def scenario_compare(db: Session, product: Product, horizon: int = 30):
    baseline = calculate_scenario(db, product, 0, 0, 0, horizon)
    cases = {
        "baseline": baseline,
        "demand_up_20": calculate_scenario(db, product, 20, 0, 0, horizon),
        "demand_down_20": calculate_scenario(db, product, -20, 0, 0, horizon),
        "lead_time_plus_7": calculate_scenario(db, product, 0, 7, 0, horizon),
        "safety_stock_plus_20": calculate_scenario(db, product, 0, 0, 20, horizon),
    }
    return {
        "product_id": product.id,
        "product": product.name,
        "sku": product.sku,
        "horizon_days": horizon,
        "scenarios": cases
    }
