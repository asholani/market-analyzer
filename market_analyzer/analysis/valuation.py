"""Valuation context (P/E vs history), free-cash-flow yield and analyst consensus.

Pure pandas logic: no Streamlit, no network access.
"""

from __future__ import annotations

import logging

import pandas as pd

from market_analyzer.analysis.fundamentals import OCF_KEYS, sorted_columns
from market_analyzer.utils.formatting import safe_get_metric

logger = logging.getLogger(__name__)

EPS_KEYS = ["Diluted EPS", "Basic EPS"]
MAX_PLAUSIBLE_PE = 250


def price_near_date(history: pd.DataFrame, date) -> float | None:
    """Closing price on `date`, or the last close before it (handles timezones)."""
    try:
        idx = history.index
        idx = idx.tz_localize(None) if idx.tz is not None else idx
        closes = pd.Series(history["Close"].values, index=idx).sort_index()
        target = pd.Timestamp(date)
        target = target.tz_localize(None) if target.tz is not None else target
        value = closes.asof(target)
        return None if pd.isna(value) else float(value)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Could not find a price near %s: %s", date, exc)
        return None


def _historical_pe(history: pd.DataFrame, income: pd.DataFrame) -> list[tuple]:
    """P/E at each of the last 5 fiscal year-ends: [(period, pe), ...]."""
    pe_hist = []
    for period in sorted_columns(income)[-5:]:
        eps = safe_get_metric(income, EPS_KEYS, period)
        price_then = price_near_date(history, period)
        if price_then is not None and eps is not None and eps > 0:
            pe = price_then / eps
            if 0 < pe < MAX_PLAUSIBLE_PE:
                pe_hist.append((period, pe))
    return pe_hist


def _year_label(period) -> str:
    return str(getattr(period, "year", str(period)[:4]))


def compute_valuation_context(
    history_10y: pd.DataFrame,
    income: pd.DataFrame | None,
    current_price: float | None,
    is_commodity: bool = False,
) -> dict | None:
    """Current P/E compared with its own 5-year average.

    Returns None for commodities. `premium_pct` is positive when the stock
    trades above its historical average multiple.
    """
    if is_commodity:
        return None

    has_income = income is not None and not income.empty
    pe_hist = _historical_pe(history_10y, income) if has_income else []

    last_eps = None
    if has_income:
        last_eps = safe_get_metric(income, EPS_KEYS, sorted_columns(income)[-1])

    current_pe = None
    if last_eps is not None and last_eps > 0 and current_price:
        current_pe = float(current_price) / last_eps

    result = {
        "current_pe": current_pe,
        "avg_pe": None,
        "history": [(_year_label(p), round(pe, 2)) for p, pe in pe_hist],
        "premium_pct": None,
        "is_loss_making": last_eps is not None and last_eps <= 0,
    }

    if len(pe_hist) >= 2:
        avg_pe = sum(pe for _, pe in pe_hist) / len(pe_hist)
        result["avg_pe"] = avg_pe
        if current_pe:
            result["premium_pct"] = (current_pe / avg_pe - 1) * 100
    return result


def compute_fcf_yield(
    cashflow: pd.DataFrame | None, market_cap: float | None, is_commodity: bool = False
) -> dict | None:
    """Free cash flow (operating cash flow + capex) and its yield on market cap.

    Capex is negative in Yahoo's cash-flow statements, hence the addition.
    """
    if is_commodity or cashflow is None or cashflow.empty:
        return None
    if not market_cap or market_cap <= 0:
        return None
    try:
        year = sorted_columns(cashflow)[-1]
    except (TypeError, ValueError, IndexError):
        return None

    ocf = safe_get_metric(cashflow, OCF_KEYS, year)
    if ocf is None:
        return None
    capex = safe_get_metric(cashflow, ["Capital Expenditure"], year) or 0.0
    fcf = ocf + capex
    return {"fcf": fcf, "yield_pct": fcf / market_cap * 100}


def _recommendation_counts(source) -> tuple[int, int, int] | None:
    """(buy, hold, sell) from a Yahoo recommendation row (dict-like or Series)."""
    try:
        buy = int(source.get("strongBuy", 0) or 0) + int(source.get("buy", 0) or 0)
        hold = int(source.get("hold", 0) or 0)
        sell = int(source.get("sell", 0) or 0) + int(source.get("strongSell", 0) or 0)
        return buy, hold, sell
    except (AttributeError, TypeError, ValueError):
        return None


def get_analyst_view(
    info: dict,
    recs_df: pd.DataFrame | None,
    current_price: float | None,
    is_commodity: bool = False,
) -> dict | None:
    """Consensus price target, upside vs current price and buy/hold/sell split."""
    if is_commodity:
        return None
    target_mean = info.get("targetMeanPrice")
    if target_mean is None or current_price is None:
        return None
    try:
        target_mean = float(target_mean)
        current_price = float(current_price)
    except (TypeError, ValueError):
        return None

    counts = None
    if isinstance(recs_df, pd.DataFrame) and not recs_df.empty:
        counts = _recommendation_counts(recs_df.iloc[-1])
    if counts is None:
        trend = info.get("recommendationTrend") or []
        if isinstance(trend, list) and trend and isinstance(trend[0], dict):
            counts = _recommendation_counts(trend[0])

    buy, hold, sell = counts or (0, 0, 0)
    total = buy + hold + sell
    distribution = None
    if total > 0:
        distribution = {
            "Buy": buy / total * 100,
            "Hold": hold / total * 100,
            "Sell": sell / total * 100,
        }

    return {
        "target_mean": target_mean,
        "target_low": info.get("targetLowPrice"),
        "target_high": info.get("targetHighPrice"),
        "n_analysts": info.get("numberOfAnalystOpinions"),
        "upside_pct": (target_mean - current_price) / current_price * 100,
        "distribution": distribution,
        "counts": {"buy": buy, "hold": hold, "sell": sell, "total": total},
        "source_reliable": counts is not None,
    }

