
def test_scenario_math():
    base_daily=100
    demand_change=20
    scenario=base_daily*(1+demand_change/100)
    assert scenario == 120
