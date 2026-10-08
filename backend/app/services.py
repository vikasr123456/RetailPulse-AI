from datetime import datetime, timedelta
import json
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import Product, Sale, Forecast, ForecastValue, Alert, AuditLog
from .forecasting.arima import prepare_series as arima_series, backtest_arima, forecast_arima
from .forecasting.lstm import prepare_series as lstm_series, run_lstm_pipeline
from .forecasting.performance import cache_key, get as cache_get, put as cache_put
from .forecasting.arima import run_arima_pipeline
from .forecasting.evaluation import evaluate_models

def product_sales_df(db, product_id, tenant_id=None, store_id=None):
    q = db.query(Sale).filter(Sale.product_id == product_id)
    if tenant_id is not None: q = q.filter(Sale.tenant_id == tenant_id)
    if store_id is not None: q = q.filter(Sale.store_id == store_id)
    rows = q.order_by(Sale.sale_date).all()
    if not rows:
        raise ValueError("No sales history exists for this product.")
    return pd.DataFrame([{"sale_date": r.sale_date, "quantity": r.quantity} for r in rows])

def generate_forecast(db: Session, product_id: int, horizon: int, tenant_id=None, store_id=None):
    """Generate a production forecast using the same leakage-safe model selection
    protocol as Model Evaluation. This prevents AUTO selection from disagreeing
    with the evaluation page because of different metrics or validation windows.
    """
    qprod = db.query(Product).filter(Product.id == product_id)
    if tenant_id is not None: qprod = qprod.filter(Product.tenant_id == tenant_id)
    if store_id is not None: qprod = qprod.filter(Product.store_id == store_id)
    product = qprod.first()
    if not product:
        raise ValueError("Product not found.")

    rows = db.query(Sale).filter(Sale.product_id == product_id)
    if tenant_id is not None: rows = rows.filter(Sale.tenant_id == tenant_id)
    if store_id is not None: rows = rows.filter(Sale.store_id == store_id)
    rows = rows.order_by(Sale.sale_date).all()
    if not rows:
        raise ValueError("No sales history exists for this product.")

    cache_id = cache_key(product_id, rows, horizon, "AUTO_EVALUATED")
    payload = cache_get(cache_id)
    if payload is None:
        comparison = evaluate_models(rows, horizon, include_forecast=True)
        winner_payload = comparison.pop("_winner_forecast")
        payload = {"comparison": comparison, "winner": winner_payload}
        cache_put(cache_id, payload)

    comparison = payload["comparison"]
    winner_payload = payload["winner"]
    selected = winner_payload["model"]
    metrics = winner_payload["metrics"]
    forecast_items = winner_payload["forecast"]
    values = np.asarray([x["value"] for x in forecast_items], dtype=float)

    # Preserve the simple forecast response while exposing the complete model
    # comparison for enterprise UI, auditability and downstream decisions.
    forecast = Forecast(
        tenant_id=tenant_id if tenant_id is not None else product.tenant_id,
        store_id=store_id if store_id is not None else product.store_id,
        product_id=product_id,
        model=selected,
        horizon=horizon,
        mae=float(metrics["mae"]),
        rmse=float(metrics["rmse"]),
        mape=float(metrics["mape"]),
        training_start=rows[0].sale_date,
        training_end=rows[-1].sale_date,
    )
    db.add(forecast)
    db.flush()
    start_date = pd.to_datetime(rows[-1].sale_date)
    for i, value in enumerate(values, start=1):
        db.add(ForecastValue(
            forecast_id=forecast.id,
            forecast_date=(start_date + pd.Timedelta(days=i)).to_pydatetime(),
            value=float(value),
        ))
    db.add(AuditLog(
        tenant_id=tenant_id if tenant_id is not None else product.tenant_id,
        store_id=store_id if store_id is not None else product.store_id,
        action="FORECAST_GENERATED",
        details=json.dumps({
            "product_id": product_id,
            "model": selected,
            "horizon": horizon,
            "selection_metric": comparison.get("primary_metric", "sMAPE"),
            "validation_days": comparison.get("validation_days"),
        }),
    ))
    db.commit()

    model_rows = {x["model"]: x for x in comparison.get("models", [])}
    return {
        "forecast_id": forecast.id,
        "product": product.name,
        "selected_model": selected,
        "metrics": {"mae": forecast.mae, "rmse": forecast.rmse, "mape": forecast.mape},
        "arima": {"metrics": model_rows.get("ARIMA", {}), "forecast": None},
        "lstm": {"metrics": model_rows.get("LSTM", {}), "forecast": None},
        "forecast": values.tolist(),
        "dates": [x["date"] for x in forecast_items],
        "evaluation": comparison,
        "model_details": {k: v for k, v in winner_payload.items() if k not in ("forecast", "metrics")},
    }

def restock_for_product(db, product_id, tenant_id=None, store_id=None, horizon=30):
    qprod = db.query(Product).filter(Product.id==product_id)
    if tenant_id is not None: qprod=qprod.filter(Product.tenant_id==tenant_id)
    if store_id is not None: qprod=qprod.filter(Product.store_id==store_id)
    product=qprod.first()
    if not product: raise ValueError("Product not found.")
    qf = db.query(Forecast).filter(Forecast.product_id==product_id)
    if tenant_id is not None: qf=qf.filter(Forecast.tenant_id==tenant_id)
    if store_id is not None: qf=qf.filter(Forecast.store_id==store_id)
    latest = qf.order_by(Forecast.created_at.desc()).first()
    if not latest:
        result = generate_forecast(db, product_id, horizon, tenant_id, store_id)
        latest = db.query(Forecast).get(result["forecast_id"])
    values = db.query(ForecastValue).filter(ForecastValue.forecast_id==latest.id).all()
    daily = sum(v.value for v in values) / max(len(values),1)
    lead_demand = daily * product.lead_time_days
    target = lead_demand + product.safety_stock
    order_qty = max(0, target - product.current_stock)
    level = "CRITICAL" if order_qty > product.current_stock else ("ATTENTION" if order_qty > 0 else "HEALTHY")
    return {
        "product_id": product.id, "product": product.name, "current_stock": product.current_stock,
        "forecast_demand": sum(v.value for v in values),
        "safety_stock": product.safety_stock, "lead_time_demand": lead_demand,
        "recommended_order": round(order_qty,2), "priority": level,
        "model": latest.model, "mape": latest.mape,
        "reason": f"{'Forecasted lead-time demand exceeds available stock.' if order_qty > 0 else 'Available stock covers configured lead-time demand.'}"
    }
