
import pandas as pd
from app.seasonality.analysis import seasonality_report, anomaly_report

def test_seasonality_report():
    idx=pd.date_range("2026-01-01",periods=21,freq="D")
    s=pd.Series([10+i%7 for i in range(21)],index=idx)
    result=seasonality_report(s)
    assert "weekday_pattern" in result
    assert len(result["weekday_pattern"]) == 7

def test_anomaly_report():
    idx=pd.date_range("2026-01-01",periods=20,freq="D")
    values=[10]*19+[100]
    result=anomaly_report(pd.Series(values,index=idx))
    assert result["anomaly_count"] >= 1
