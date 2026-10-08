import numpy as np

def _arrays(actual, pred):
    a, p = np.asarray(actual, dtype=float), np.asarray(pred, dtype=float)
    return a, p

def mae(actual, pred):
    a, p = _arrays(actual, pred)
    return float(np.mean(np.abs(a - p)))

def rmse(actual, pred):
    a, p = _arrays(actual, pred)
    return float(np.sqrt(np.mean((a - p) ** 2)))

def mape(actual, pred):
    a, p = _arrays(actual, pred)
    mask = np.abs(a) > 1e-9
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs((a[mask] - p[mask]) / a[mask])) * 100)

def smape(actual, pred):
    a, p = _arrays(actual, pred)
    denom = np.abs(a) + np.abs(p)
    mask = denom > 1e-9
    if not np.any(mask):
        return 0.0
    return float(np.mean(2.0 * np.abs(p[mask] - a[mask]) / denom[mask]) * 100)

def wmape(actual, pred):
    a, p = _arrays(actual, pred)
    denom = np.sum(np.abs(a))
    if denom <= 1e-9:
        return 0.0
    return float(np.sum(np.abs(a - p)) / denom * 100)

def accuracy_from_smape(value):
    # Bounded, interpretable accuracy proxy for model comparison.
    return float(max(0.0, min(100.0, 100.0 - float(value))))
