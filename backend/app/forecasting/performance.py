from __future__ import annotations
from time import perf_counter
from typing import Any

# Small in-process cache. It is intentionally keyed by the active dataset
# signature so a newly uploaded dataset never reuses an old forecast.
_CACHE: dict[tuple[Any, ...], Any] = {}
_MAX_ITEMS = 64


def dataset_signature(rows) -> tuple:
    if not rows:
        return (0, None, None)
    first = rows[0]
    last = rows[-1]
    return (
        len(rows),
        str(getattr(first, "sale_date", "")),
        str(getattr(last, "sale_date", "")),
    )


def cache_key(product_id: int, rows, horizon: int, model: str) -> tuple:
    return (int(product_id), dataset_signature(rows), int(horizon), str(model).upper())


def get(key):
    return _CACHE.get(key)


def put(key, value):
    if len(_CACHE) >= _MAX_ITEMS:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = value
    return value


def clear():
    _CACHE.clear()


def timed_call(fn, *args, **kwargs):
    started = perf_counter()
    result = fn(*args, **kwargs)
    return result, round(perf_counter() - started, 3)
