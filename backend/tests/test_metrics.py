
from app.forecasting.metrics import mae, rmse, mape

def test_mae():
    assert mae([1,2,3],[1,3,5]) == 1.0

def test_rmse():
    assert round(rmse([1,2,3],[1,3,5]),6) == round((5/3)**0.5,6)

def test_mape_ignores_zero_actuals():
    assert mape([0,100],[50,110]) == 10.0
