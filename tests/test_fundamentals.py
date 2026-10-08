import numpy as np
import pandas as pd

from market_analyzer.analysis.fundamentals import (
    compute_debt_metrics,
    compute_dividend_metrics,
    compute_growth_trends,
    compute_piotroski,
)


def make_income():
    cols = pd.to_datetime(["2021-12-31", "2022-12-31", "2023-12-31"])
    return pd.DataFrame(
        {
            cols[0]: [100.0, 10.0, 40.0],
            cols[1]: [110.0, 12.0, 46.0],
            cols[2]: [121.0, 15.0, 55.0],
        },
        index=["Total Revenue", "Net Income", "Gross Profit"],
    )


def test_growth_trends_cagr():
    res = compute_growth_trends(make_income(), current_year=2023)
    assert res["labels"] == ["2021", "2022", "2023"]
    assert res["n_years"] == 2
    assert abs(res["revenue_cagr"] - 10.0) < 1e-6  # 100 -> 121 over 2 years = 10% a year
    assert res["target_year"] == "2023"


def test_growth_trends_none_for_commodity_or_empty():
    assert compute_growth_trends(make_income(), is_commodity=True) is None
    assert compute_growth_trends(None) is None
    assert compute_growth_trends(pd.DataFrame()) is None


def test_dividend_metrics_converts_to_percent():
    res = compute_dividend_metrics({"dividendRate": 2.0, "dividendYield": 0.025, "payoutRatio": 0.4})
    assert res["yield_pct"] == 2.5
    assert res["payout_pct"] == 40.0
    assert compute_dividend_metrics({}, is_commodity=True) is None


def test_debt_metrics():
    bal = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [500.0, 200.0]},
        index=["Total Debt", "Stockholders Equity"],
    )
    inc = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [60.0, -20.0]},
        index=["EBIT", "Interest Expense"],
    )
    res = compute_debt_metrics(bal, inc)
    assert res["debt_to_equity"] == 2.5
    assert res["interest_coverage"] == 3.0


def test_debt_metrics_skipped_for_financials():
    assert compute_debt_metrics(pd.DataFrame(), pd.DataFrame(), is_financial=True) is None


def test_piotroski_perfect_score_on_improving_company():
    years = pd.to_datetime(["2022-12-31", "2023-12-31"])
    income = pd.DataFrame(
        {years[0]: [100.0, 10.0, 40.0], years[1]: [120.0, 15.0, 54.0]},
        index=["Total Revenue", "Net Income", "Gross Profit"],
    )
    balance = pd.DataFrame(
        {years[0]: [200.0, 50.0, 40.0, 30.0, 100.0], years[1]: [200.0, 40.0, 60.0, 30.0, 100.0]},
        index=["Total Assets", "Long Term Debt", "Current Assets", "Current Liabilities", "Ordinary Shares Number"],
    )
    cashflow = pd.DataFrame(
        {years[0]: [12.0], years[1]: [20.0]},
        index=["Operating Cash Flow"],
    )
    res = compute_piotroski(income, balance, cashflow)
    assert res["score"] == res["max_score"] == 9
    assert all(res["criteria"].values())


def test_piotroski_none_when_data_missing():
    assert compute_piotroski(None, None, None) is None
    assert compute_piotroski(make_income(), make_income(), pd.DataFrame()) is None
    assert compute_piotroski(make_income(), make_income(), make_income(), is_financial=True) is None

