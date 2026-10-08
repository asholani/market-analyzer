import numpy as np
import pandas as pd

from market_analyzer.ui.charts import (
    analyst_chart,
    price_chart,
    return_distribution_chart,
    revenue_net_income_chart,
)


def make_history(n=60):
    idx = pd.date_range("2024-01-01", periods=n, freq="D", name="Date")
    return pd.DataFrame({"Close": np.linspace(100, 120, n)}, index=idx)


def test_price_chart_without_benchmark():
    chart = price_chart(make_history(), "AAPL", "$")
    assert chart.to_dict()


def test_price_chart_with_benchmark():
    chart = price_chart(make_history(), "AAPL", "$", make_history(), "S&P 500")
    assert chart.to_dict()


def test_price_chart_ignores_empty_benchmark():
    chart = price_chart(make_history(), "AAPL", "$", pd.DataFrame(), "S&P 500")
    assert chart.to_dict()


def test_revenue_net_income_chart():
    assert revenue_net_income_chart(1_000.0, 150.0, "$").to_dict()


def test_analyst_chart():
    assert analyst_chart({"Buy": 60.0, "Hold": 30.0, "Sell": 10.0}).to_dict()


def test_return_distribution_chart():
    rets = pd.Series(np.random.default_rng(0).normal(0, 1, 500))
    assert return_distribution_chart(rets, -2.7, -3.5).to_dict()

