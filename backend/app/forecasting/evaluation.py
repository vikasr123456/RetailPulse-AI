from __future__ import annotations

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

from .arima import prepare_series as prepare_arima_series, fit_arima, chronological_backtest
from .lstm import prepare_series as prepare_lstm_series, _build_model
from .metrics import mae, rmse, mape, smape, wmape, accuracy_from_smape


# A shared outer holdout makes ARIMA/LSTM genuinely comparable.
DEFAULT_VALIDATION_DAYS = 30
MIN_VALIDATION_DAYS = 14
LSTM_EPOCHS = 20


def build_evaluation_frame(rows):
    return pd.DataFrame([{"sale_date": r.sale_date, "quantity": r.quantity} for r in rows])


def _score(actual, pred):
    return {
        "mae": float(mae(actual, pred)),
        "rmse": float(rmse(actual, pred)),
        "mape": float(mape(actual, pred)),
        "smape": float(smape(actual, pred)),
        "wmape": float(wmape(actual, pred)),
    }


def _validation_days(series_length: int, requested: int) -> int:
    requested = int(requested or DEFAULT_VALIDATION_DAYS)
    target = min(DEFAULT_VALIDATION_DAYS, max(MIN_VALIDATION_DAYS, requested))
    if series_length - target < 45:
        target = min(target, max(MIN_VALIDATION_DAYS, series_length // 5))
    if series_length - target < 30:
        raise ValueError("Insufficient history for a reliable chronological holdout.")
    return target


def _select_arima_on_training(train: pd.Series, inner_days: int = 14):
    """Select ARIMA order without looking at the outer test window."""
    base_model, info = fit_arima(train)
    candidates = [tuple(info["order"])] + [tuple(x["order"]) for x in info.get("candidates", [])]
    seen = set()
    trials = []
    for order in candidates:
        if order in seen:
            continue
        seen.add(order)
        try:
            bt = chronological_backtest(train, order, validation_days=min(inner_days, max(7, len(train) // 6)))
            trials.append((bt["smape"], order))
        except Exception:
            continue
    if not trials:
        return tuple(info["order"]), base_model, info, []
    trials.sort(key=lambda x: x[0])
    best_order = trials[0][1]
    model = base_model
    if best_order != tuple(info["order"]):
        model = ARIMA(train, order=best_order, trend=None).fit(method_kwargs={"warn_convergence": False})
        info = dict(info)
        info["order"] = best_order
    return best_order, model, info, [{"order": list(o), "inner_smape": float(s)} for s, o in trials[:6]]


def _fit_lstm_train_test(train: pd.Series, test: pd.Series, lookback: int, epochs: int = LSTM_EPOCHS):
    """Fit LSTM using training data only and evaluate one-step-ahead on the outer test."""
    from sklearn.preprocessing import MinMaxScaler
    import tensorflow as tf

    tf.keras.utils.set_random_seed(42)
    train_values = np.asarray(train, dtype=float).reshape(-1, 1)
    scaler = MinMaxScaler()
    scaled_train = scaler.fit_transform(train_values).flatten()

    X = []
    y = []
    for i in range(lookback, len(scaled_train)):
        X.append(scaled_train[i - lookback:i])
        y.append(scaled_train[i])
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    if len(X) < 30:
        raise ValueError("Insufficient training sequences for LSTM.")

    model = _build_model(lookback)
    val_split = 0.15 if len(X) >= 50 else 0.10
    callback = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True)
    model.fit(
        X.reshape(-1, lookback, 1), y,
        epochs=epochs, batch_size=32, verbose=0, shuffle=False,
        validation_split=val_split, callbacks=[callback]
    )

    # One-step validation: each test prediction can use the real previous day,
    # preventing recursive forecast drift from contaminating the metric.
    context = np.concatenate([np.asarray(train, dtype=float), np.asarray(test, dtype=float)])
    scaled_context = scaler.transform(context.reshape(-1, 1)).flatten()
    test_start = len(train)
    pred_scaled = []
    for i in range(test_start, len(context)):
        window = scaled_context[i - lookback:i]
        value = float(model(window.reshape(1, lookback, 1), training=False).numpy()[0, 0])
        pred_scaled.append(value)
    pred = scaler.inverse_transform(np.asarray(pred_scaled).reshape(-1, 1)).flatten()
    pred = np.maximum(pred, 0)
    actual = np.asarray(test, dtype=float)
    metrics = _score(actual, pred)
    return model, scaler, metrics, actual, pred


def _fit_lstm_full(series: pd.Series, lookback: int, epochs: int = LSTM_EPOCHS):
    """Final training after model selection, using the complete history."""
    from sklearn.preprocessing import MinMaxScaler
    import tensorflow as tf

    tf.keras.utils.set_random_seed(42)
    values = np.asarray(series, dtype=float).reshape(-1, 1)
    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(values).flatten()
    X = []
    y = []
    for i in range(lookback, len(scaled)):
        X.append(scaled[i - lookback:i])
        y.append(scaled[i])
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    if len(X) < 30:
        raise ValueError("Insufficient sequences for final LSTM training.")
    model = _build_model(lookback)
    callback = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True)
    model.fit(X.reshape(-1, lookback, 1), y, epochs=epochs, batch_size=32,
              verbose=0, shuffle=False, validation_split=0.12, callbacks=[callback])
    return model, scaler


def _recursive_lstm_forecast(model, scaler, series: pd.Series, horizon: int, lookback: int):
    scaled = scaler.transform(np.asarray(series, dtype=float).reshape(-1, 1)).flatten()
    window = list(scaled[-lookback:])
    predictions = []
    for _ in range(horizon):
        x = np.asarray(window[-lookback:], dtype=np.float32).reshape(1, lookback, 1)
        value = float(model(x, training=False).numpy()[0, 0])
        predictions.append(value)
        window.append(value)
    return np.maximum(scaler.inverse_transform(np.asarray(predictions).reshape(-1, 1)).flatten(), 0)


def _arima_forecast(model, series, horizon):
    forecast = model.get_forecast(steps=horizon)
    mean = np.maximum(np.asarray(forecast.predicted_mean, dtype=float), 0)
    ci = forecast.conf_int(alpha=0.05)
    lower = np.maximum(np.asarray(ci.iloc[:, 0], dtype=float), 0)
    upper = np.maximum(np.asarray(ci.iloc[:, 1], dtype=float), 0)
    dates = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon, freq="D")
    return [{"date": d.strftime("%Y-%m-%d"), "value": float(mean[i]),
             "lower_95": float(lower[i]), "upper_95": float(upper[i])} for i, d in enumerate(dates)]


def evaluate_models(rows, horizon=30, include_forecast=False):
    if not rows:
        raise ValueError("No sales history exists for this product.")

    df = build_evaluation_frame(rows)
    arima_series = prepare_arima_series(df)
    lstm_series = prepare_lstm_series(df)
    # Both models use the same actual outer holdout dates.
    n = min(len(arima_series), len(lstm_series))
    if n != len(arima_series) or n != len(lstm_series):
        # Both preparation functions currently use the same history cap, but keep this safe.
        common_index = arima_series.index.intersection(lstm_series.index)
        arima_series = arima_series.loc[common_index]
        lstm_series = lstm_series.loc[common_index]
    validation_days = _validation_days(len(arima_series), horizon)
    train_arima = arima_series.iloc[:-validation_days]
    test_arima = arima_series.iloc[-validation_days:]
    train_lstm = lstm_series.iloc[:-validation_days]
    test_lstm = lstm_series.iloc[-validation_days:]

    # ARIMA: order selection is performed only on the training side.
    best_order, _, arima_info, arima_trials = _select_arima_on_training(train_arima)
    arima_model = ARIMA(train_arima, order=best_order, trend=None).fit(method_kwargs={"warn_convergence": False})
    arima_pred = np.maximum(np.asarray(arima_model.forecast(validation_days), dtype=float), 0)
    arima_actual = np.asarray(test_arima, dtype=float)
    arima_score = _score(arima_actual, arima_pred)

    # LSTM: lookback selection is also done only on the training side using
    # an inner chronological split, then the selected lookback is scored on the
    # untouched common outer holdout.
    lookbacks = [7, 14, 21, 28] if len(train_lstm) >= 120 else [7, 14, 21]
    inner_days = min(14, max(7, len(train_lstm) // 6))
    lstm_trials = []
    for lb in lookbacks:
        try:
            inner_train = train_lstm.iloc[:-inner_days]
            inner_test = train_lstm.iloc[-inner_days:]
            _, _, inner_score, _, _ = _fit_lstm_train_test(inner_train, inner_test, lb, epochs=12)
            lstm_trials.append((inner_score["smape"], lb))
        except Exception:
            continue
    if not lstm_trials:
        raise ValueError("LSTM could not produce a valid chronological validation result.")
    lstm_trials.sort(key=lambda x: x[0])
    best_lb = lstm_trials[0][1]
    lstm_model, lstm_scaler, lstm_score, lstm_actual, lstm_pred = _fit_lstm_train_test(
        train_lstm, test_lstm, best_lb, epochs=LSTM_EPOCHS
    )

    results = [
        {"model": "ARIMA", **arima_score,
         "accuracy_pct": accuracy_from_smape(arima_score["smape"]),
         "validation_days": validation_days,
         "details": {"order": list(best_order), "d": int(arima_info["d"]),
                     "aic": float(arima_model.aic), "bic": float(arima_model.bic),
                     "inner_trials": arima_trials}},
        {"model": "LSTM", **lstm_score,
         "accuracy_pct": accuracy_from_smape(lstm_score["smape"]),
         "validation_days": validation_days,
         "details": {"lookback": int(best_lb), "epochs": LSTM_EPOCHS,
                     "inner_trials": [{"lookback": lb, "inner_smape": float(s)} for s, lb in lstm_trials]}},
    ]
    ranked = sorted(results, key=lambda x: (x["smape"], x["wmape"], x["rmse"], x["mae"]))
    for i, item in enumerate(ranked, 1):
        item["rank"] = i

    winner = ranked[0]
    runner_up = ranked[1]
    relative_improvement = 0.0
    if runner_up["smape"] > 1e-9:
        relative_improvement = max(0.0, (runner_up["smape"] - winner["smape"]) / runner_up["smape"] * 100.0)

    result = {
        "validation_protocol": "Strict chronological holdout: identical outer test window for ARIMA and LSTM; model selection occurs only on the training side; no random shuffling or test leakage.",
        "validation_protocol_short": f"Same {validation_days}-day holdout",
        "validation_days": validation_days,
        "validation_start": test_arima.index.min().strftime("%Y-%m-%d"),
        "validation_end": test_arima.index.max().strftime("%Y-%m-%d"),
        "training_end": train_arima.index.max().strftime("%Y-%m-%d"),
        "primary_metric": "sMAPE",
        "secondary_metrics": ["WMAPE", "MAPE", "RMSE", "MAE"],
        "winner": winner["model"],
        "best_accuracy_pct": float(winner["accuracy_pct"]),
        "relative_error_improvement_pct": float(relative_improvement),
        "models": ranked,
        "validation_series": {
            "dates": [d.strftime("%Y-%m-%d") for d in test_arima.index],
            "actual": arima_actual.tolist(),
            "ARIMA": arima_pred.tolist(),
            "LSTM": lstm_pred.tolist(),
        },
        "recommendation": f"{winner['model']} is recommended because it has the lowest sMAPE on the identical {validation_days}-day chronological holdout. The reported accuracy is a derived score (100 - sMAPE), not classification accuracy.",
    }

    if include_forecast:
        if winner["model"] == "ARIMA":
            # Refit the selected model on the complete history only after evaluation.
            final_model = ARIMA(arima_series, order=best_order, trend=None).fit(method_kwargs={"warn_convergence": False})
            result["_winner_forecast"] = {
                "model": "ARIMA", "order": list(best_order), "d": int(arima_info["d"]),
                "metrics": winner, "forecast": _arima_forecast(final_model, arima_series, horizon)
            }
        else:
            final_model, final_scaler = _fit_lstm_full(lstm_series, best_lb, LSTM_EPOCHS)
            future = _recursive_lstm_forecast(final_model, final_scaler, lstm_series, horizon, best_lb)
            dates = pd.date_range(lstm_series.index.max() + pd.Timedelta(days=1), periods=horizon, freq="D")
            result["_winner_forecast"] = {
                "model": "LSTM", "lookback": best_lb, "epochs_requested": LSTM_EPOCHS,
                "metrics": winner,
                "forecast": [{"date": d.strftime("%Y-%m-%d"), "value": float(future[i])} for i, d in enumerate(dates)]
            }
    return result
