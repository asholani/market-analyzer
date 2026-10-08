import numpy as np
import pandas as pd

from market_analyzer.analysis.valuation import (
    compute_fcf_yield,
    compute_valuation_context,
    get_analyst_view,
    price_near_date,
)


def make_history():
    idx = pd.date_range("2019-01-01", "2024-12-31", freq="D", tz="America/New_York")
    return pd.DataFrame({"Close": np.linspace(50.0, 150.0, len(idx))}, index=idx)


def make_income(eps_values):
    cols = pd.to_datetime([f"{2019 + i}-12-31" for i in range(len(eps_values))])
    return pd.DataFrame([eps_values], columns=cols, index=["Diluted EPS"])


def test_price_near_date_handles_timezone():
    price = price_near_date(make_history(), pd.Timestamp("2022-06-30"))
    assert price is not None and 50.0 < price < 150.0


def test_valuation_context_computes_premium():
    income = make_income([5.0, 5.0, 5.0, 5.0, 5.0])
    res = compute_valuation_context(make_history(), income, current_price=200.0)
    assert res["current_pe"] == 40.0  # 200 / 5
    assert res["avg_pe"] is not None
    assert res["premium_pct"] is not None
    assert res["is_loss_making"] is False


def test_valuation_context_flags_loss_making():
    income = make_income([-1.0, -1.0, -1.0])
    res = compute_valuation_context(make_history(), income, current_price=50.0)
    assert res["is_loss_making"] is True
    assert res["current_pe"] is None


def test_valuation_context_none_for_commodity():
    assert compute_valuation_context(make_history(), None, 100.0, is_commodity=True) is None


def test_fcf_yield():
    cf = pd.DataFrame(
        {pd.Timestamp("2023-12-31"): [150.0, -50.0]},
        index=["Operating Cash Flow", "Capital Expenditure"],
    )
    res = compute_fcf_yield(cf, market_cap=2000.0)
    assert res["fcf"] == 100.0
    assert res["yield_pct"] == 5.0
    assert compute_fcf_yield(cf, market_cap=None) is None
    assert compute_fcf_yield(None, market_cap=2000.0) is None


def test_analyst_view_upside_and_distribution():
    info = {"targetMeanPrice": 120.0, "numberOfAnalystOpinions": 10}
    recs = pd.DataFrame([{"strongBuy": 2, "buy": 4, "hold": 3, "sell": 1, "strongSell": 0}])
    res = get_analyst_view(info, recs, current_price=100.0)
    assert res["upside_pct"] == 20.0
    assert res["counts"] == {"buy": 6, "hold": 3, "sell": 1, "total": 10}
    assert abs(res["distribution"]["Buy"] - 60.0) < 1e-9


def test_analyst_view_none_without_target():
    assert get_analyst_view({}, None, 100.0) is None
    assert get_analyst_view({"targetMeanPrice": 120.0}, None, None) is None
    assert get_analyst_view({"targetMeanPrice": 120.0}, None, 100.0, is_commodity=True) is None# -*- coding: utf-8 -*-

