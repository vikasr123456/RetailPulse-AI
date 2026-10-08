
from __future__ import annotations
import numpy as np
import pandas as pd

def prepare_daily(rows):
    if not rows:
        raise ValueError("No sales history exists.")
    df=pd.DataFrame([{"date":r.sale_date,"quantity":r.quantity} for r in rows])
    df["date"]=pd.to_datetime(df["date"],errors="coerce")
    df["quantity"]=pd.to_numeric(df["quantity"],errors="coerce")
    df=df.dropna().groupby("date")["quantity"].sum().sort_index()
    full=pd.date_range(df.index.min(),df.index.max(),freq="D")
    return df.reindex(full,fill_value=0.0).astype(float)

def seasonality_report(series:pd.Series):
    if len(series)<14:
        raise ValueError("At least 14 daily observations are required.")
    s=series.astype(float)
    weekday=s.groupby(s.index.dayofweek).mean()
    monthly=s.groupby(s.index.month).mean()

    baseline=float(s.mean())
    weekday_effect=[
        {
            "day":int(i),
            "label":["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][i],
            "average":round(float(v),2),
            "index":round(float(v/baseline),3) if baseline else None
        }
        for i,v in weekday.items()
    ]
    month_effect=[
        {"month":int(i),"average":round(float(v),2),
         "index":round(float(v/baseline),3) if baseline else None}
        for i,v in monthly.items()
    ]
    strongest_weekday=max(weekday_effect,key=lambda x:x["average"])
    weakest_weekday=min(weekday_effect,key=lambda x:x["average"])

    return {
        "baseline_daily_demand":round(baseline,2),
        "weekday_pattern":weekday_effect,
        "monthly_pattern":month_effect,
        "strongest_weekday":strongest_weekday,
        "weakest_weekday":weakest_weekday,
        "pattern_strength":round(float(s.std()/baseline),3) if baseline else 0
    }

def anomaly_report(series:pd.Series, window=14, z_threshold=2.5):
    s=series.astype(float)
    if len(s)<window+3:
        raise ValueError("Not enough history for anomaly detection.")
    rolling_mean=s.rolling(window,min_periods=window).mean()
    rolling_std=s.rolling(window,min_periods=window).std().replace(0,np.nan)
    z=(s-rolling_mean)/rolling_std
    anomalies=[]
    for idx,value in z.dropna().items():
        if abs(float(value))>=z_threshold:
            kind="SPIKE" if value>0 else "DROP"
            anomalies.append({
                "date":idx.strftime("%Y-%m-%d"),
                "actual":round(float(s.loc[idx]),2),
                "rolling_mean":round(float(rolling_mean.loc[idx]),2),
                "z_score":round(float(value),2),
                "type":kind,
                "severity":"HIGH" if abs(value)>=3.5 else "MEDIUM"
            })
    return {
        "method":"rolling z-score",
        "window_days":window,
        "threshold":z_threshold,
        "anomaly_count":len(anomalies),
        "anomalies":anomalies[-50:]
    }
