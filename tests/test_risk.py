import numpy as np
import pandas as pd

from market_analyzer.analysis.risk import (
    Z_95,
    compute_capm,
    compute_risk_metrics,
    cornish_fisher_z,
    resolve_benchmark_ticker,
)


def make_prices(n=800, vol=0.01, drift=0.0003, seed=0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    idx = pd.bdate_range(end="2024-12-31", periods=n)
    return pd.Series(100 * np.cumprod(1 + rets), index=idx)


def test_resolve_benchmark():
    assert resolve_benchmark_ticker("AIR.PA") == ("^FCHI", "CAC 40")
    assert resolve_benchmark_ticker("SAP.DE") == ("^GDAXI", "DAX 40")
    assert resolve_benchmark_ticker("7203.T") == ("^N225", "Nikkei 225")
    assert resolve_benchmark_ticker("AAPL") == ("^GSPC", "S&P 500")
    assert resolve_benchmark_ticker("GC=F") == (None, None)


def test_cornish_fisher_reduces_to_normal_quantile():
    assert cornish_fisher_z(Z_95, 0.0, 0.0) == Z_95


def test_cornish_fisher_fat_tails_increase_quantile():
    assert cornish_fisher_z(Z_95, 0.0, 3.0) > Z_95 - 0.5  # sanity: finite and close
    assert cornish_fisher_z(2.326348, 0.0, 3.0) > 2.326348  # 99% quantile widens with kurtosis


def test_volatility_close_to_input():
    res = compute_risk_metrics(make_prices(vol=0.01))
    expected = 0.01 * np.sqrt(252) * 100
    assert abs(res["annualized_volatility"] - expected) < 2.0


def test_tail_ordering():
    res = compute_risk_metrics(make_prices())
    assert res["hist_var_99_1d"] > res["hist_var_95_1d"] > 0
    assert res["hist_cvar_95_1d"] >= res["hist_var_95_1d"]
    assert res["hist_cvar_99_1d"] >= res["hist_var_99_1d"]


def test_parametric_var_close_to_historical_for_normal_returns():
    res = compute_risk_metrics(make_prices(n=2000))
    assert abs(res["param_var_95_1d"] - res["hist_var_95_1d"]) < 0.3


def test_max_drawdown_is_negative_and_bounded():
    res = compute_risk_metrics(make_prices())
    assert -100 < res["max_drawdown"] < 0


def test_beta_of_scaled_benchmark_is_the_scale():
    bench = make_prices(seed=1)
    bench_rets = bench.pct_change().dropna()
    asset_rets = 1.5 * bench_rets
    asset = 100 * (1 + asset_rets).cumprod()
    asset = pd.concat([pd.Series([100.0], index=[bench.index[0]]), asset])
    res = compute_risk_metrics(asset, bench_close=bench)
    assert abs(res["beta"] - 1.5) < 0.05
    assert res["r_squared"] > 0.99


def test_capm_without_benchmark_reports_error():
    res = compute_capm(pd.Series([0.01, -0.01]), None, 0.03)
    assert res["beta"] is None
    assert res["error"]


def test_too_little_history_returns_none():
    assert compute_risk_metrics(make_prices(n=30)) is None# -*- coding: utf-8 -*-

