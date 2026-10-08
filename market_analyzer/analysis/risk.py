"""Quantitative market-risk metrics (volatility, VaR, CVaR, Cornish-Fisher, CAPM, Sharpe/Sortino).

Pure pandas/numpy/scipy logic: takes price Series as input, never downloads anything.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

from market_analyzer.config import TRADING_DAYS

logger = logging.getLogger(__name__)

MIN_OBSERVATIONS = 60
Z_95 = 1.644853
Z_99 = 2.326348

# ticker suffix -> (benchmark symbol, display name)
BENCHMARKS = {
    ".PA": ("^FCHI", "CAC 40"),
    ".DE": ("^GDAXI", "DAX 40"),
    ".T": ("^N225", "Nikkei 225"),
    ".HK": ("^HSI", "Hang Seng Index"),
    ".SS": ("000001.SS", "SSE Composite"),
    ".SZ": ("000001.SS", "SSE Composite"),
    ".L": ("^FTSE", "FTSE 100"),
}
DEFAULT_BENCHMARK = ("^GSPC", "S&P 500")


def resolve_benchmark_ticker(ticker: str) -> tuple[str | None, str | None]:
    """Regional benchmark (symbol, name) for a ticker; (None, None) for futures."""
    ticker_up = str(ticker).upper()
    if ticker_up.endswith("=F"):
        return None, None
    for suffix, benchmark in BENCHMARKS.items():
        if ticker_up.endswith(suffix):
            return benchmark
    return DEFAULT_BENCHMARK


def cornish_fisher_z(z: float, skew: float, excess_kurtosis: float) -> float:
    """Cornish-Fisher expansion of a normal quantile z using skewness and excess kurtosis."""
    return (
        z
        + (z**2 - 1) * skew / 6
        + (z**3 - 3 * z) * excess_kurtosis / 24
        - (2 * z**3 - 5 * z) * skew**2 / 36
    )


def _last_years(close: pd.Series, years: int) -> pd.Series:
    """Keep only the last `years` years of a price Series."""
    cutoff = close.index.max() - pd.Timedelta(days=years * 365)
    return close[close.index >= cutoff]


def _tail_metrics(returns: pd.Series) -> dict:
    """Historical VaR and expected shortfall (CVaR), as positive loss percentages."""
    var_95 = float(-np.percentile(returns, 5) * 100)
    var_99 = float(-np.percentile(returns, 1) * 100)
    tail_95 = returns[returns <= -var_95 / 100]
    tail_99 = returns[returns <= -var_99 / 100]
    return {
        "hist_var_95_1d": var_95,
        "hist_var_99_1d": var_99,
        "hist_cvar_95_1d": float(-tail_95.mean() * 100) if len(tail_95) else var_95,
        "hist_cvar_99_1d": float(-tail_99.mean() * 100) if len(tail_99) else var_99,
    }


def _parametric_metrics(returns: pd.Series) -> dict:
    """Normal-assumption VaR and the Cornish-Fisher modified VaR (positive loss %)."""
    mean, vol = returns.mean(), returns.std()
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns))
    var_95 = float(-(mean - Z_95 * vol) * 100)
    var_99 = float(-(mean - Z_99 * vol) * 100)
    z_cf = cornish_fisher_z(Z_95, skew, kurt)
    return {
        "param_var_95_1d": var_95,
        "param_var_99_1d": var_99,
        "param_var_95_10d": float(var_95 * np.sqrt(10)),
        "cf_mod_var_95_1d": float(-(mean - z_cf * vol) * 100),
        "skewness": skew,
        "kurtosis": kurt,
    }


def _ratio_metrics(returns: pd.Series, risk_free_rate: float) -> dict:
    """Sharpe and Sortino ratios (annualized)."""
    daily_rf = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = returns - daily_rf
    vol = returns.std()
    downside_std = returns[returns < daily_rf].std()
    return {
        "sharpe_ratio": float(excess.mean() / vol * np.sqrt(TRADING_DAYS)) if vol > 0 else None,
        "sortino_ratio": (
            float(excess.mean() / downside_std * np.sqrt(TRADING_DAYS))
            if (downside_std and downside_std > 0)
            else None
        ),
    }


def compute_capm(
    returns: pd.Series, bench_returns: pd.Series | None, risk_free_rate: float
) -> dict:
    """Beta, Jensen's alpha (annualized %), R-squared and an optional error message."""
    out = {"beta": None, "alpha": None, "r_squared": None, "error": None}
    if bench_returns is None or bench_returns.empty:
        out["error"] = "No benchmark data available."
        return out

    aligned = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
    if len(aligned) < MIN_OBSERVATIONS:
        out["error"] = "Insufficient overlapping history with the benchmark to estimate Beta."
        return out

    y, x = aligned.iloc[:, 0], aligned.iloc[:, 1]
    var_x = np.cov(y, x)[1, 1]
    if var_x <= 0:
        out["error"] = "Zero variance for the benchmark."
        return out

    beta = float(np.cov(y, x)[0, 1] / var_x)
    asset_ann = y.mean() * TRADING_DAYS
    bench_ann = x.mean() * TRADING_DAYS
    out["beta"] = beta
    out["alpha"] = float((asset_ann - (risk_free_rate + beta * (bench_ann - risk_free_rate))) * 100)
    out["r_squared"] = float(np.corrcoef(y, x)[0, 1] ** 2)
    return out


def compute_risk_metrics(
    close: pd.Series,
    bench_close: pd.Series | None = None,
    risk_free_rate: float = 0.03,
) -> dict | None:
    """All risk metrics over the last 5 years of daily closes.

    `bench_close` is optional; without it beta/alpha/R-squared stay None.
    VaR/CVaR values are positive loss percentages (e.g. 2.1 means a 2.1% loss).
    Returns None if there is too little history.
    """
    close = close.dropna()
    if len(close) < MIN_OBSERVATIONS:
        return None

    close_5y = _last_years(close, 5)
    if len(close_5y) < MIN_OBSERVATIONS:
        close_5y = close

    returns = close_5y.pct_change().dropna()
    daily_vol = returns.std()

    one_year = _last_years(close_5y, 1)
    one_year_return = (
        float((one_year.iloc[-1] / one_year.iloc[0] - 1) * 100) if len(one_year) >= 2 else None
    )
    max_drawdown = float((close_5y / close_5y.cummax() - 1).min() * 100)

    bench_returns = None
    if bench_close is not None and not bench_close.dropna().empty:
        bench_returns = _last_years(bench_close.dropna(), 5).pct_change().dropna()
    capm = compute_capm(returns, bench_returns, risk_free_rate)

    return {
        "returns_series": returns,
        "annualized_volatility": float(daily_vol * np.sqrt(TRADING_DAYS) * 100),
        "daily_volatility": float(daily_vol * 100),
        "one_year_return": one_year_return,
        "max_drawdown": max_drawdown,
        **_ratio_metrics(returns, risk_free_rate),
        **_tail_metrics(returns),
        **_parametric_metrics(returns),
        "beta": capm["beta"],
        "alpha": capm["alpha"],
        "r_squared": capm["r_squared"],
        "benchmark_error": capm["error"],
    }# -*- coding: utf-8 -*-

