"""Fundamental analysis: growth, dividends, leverage and Piotroski F-score.

Pure pandas/numpy logic: no Streamlit, no network access.
"""

from __future__ import annotations

import logging

import pandas as pd

from market_analyzer.utils.formatting import safe_get_metric

logger = logging.getLogger(__name__)

REVENUE_KEYS = ["Total Revenue", "Operating Revenue"]
NET_INCOME_KEYS = ["Net Income", "Net Income Common Stockholders"]
OCF_KEYS = ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]
LT_DEBT_KEYS = ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]
SHARES_KEYS = ["Ordinary Shares Number", "Share Issued"]


def sorted_columns(df: pd.DataFrame) -> list:
    """Return the statement's period columns sorted from oldest to newest."""
    return sorted(df.columns, key=pd.to_datetime)


# ----------------------------------------------------------------------
# Growth
# ----------------------------------------------------------------------
def _annual_records(income: pd.DataFrame) -> dict[str, dict[str, float]]:
    """Extract {year: {revenue, net_income}} from the annual income statement."""
    records = {}
    for col in income.columns:
        try:
            year = str(pd.to_datetime(col).year)
        except (TypeError, ValueError):
            continue
        rev = safe_get_metric(income, REVENUE_KEYS, col)
        ni = safe_get_metric(income, NET_INCOME_KEYS, col)
        if rev is not None and ni is not None:
            records[year] = {"revenue": rev, "net_income": ni}
    return records


def _ttm_record(quarterly_income: pd.DataFrame) -> dict[str, float] | None:
    """Trailing-twelve-months revenue/net income from the last 4 quarters."""
    try:
        last_4 = sorted_columns(quarterly_income)[-4:]
    except (TypeError, ValueError):
        return None
    revenue = sum(safe_get_metric(quarterly_income, REVENUE_KEYS, q) or 0 for q in last_4)
    net_income = sum(safe_get_metric(quarterly_income, NET_INCOME_KEYS, q) or 0 for q in last_4)
    if revenue > 0:
        return {"revenue": revenue, "net_income": net_income}
    return None


def compute_growth_trends(
    income: pd.DataFrame | None,
    quarterly_income: pd.DataFrame | None = None,
    is_commodity: bool = False,
    current_year: int | None = None,
) -> dict | None:
    """Revenue and net income over the last 5 fiscal years, plus revenue CAGR.

    If the current year is not yet reported, a TTM figure built from the last
    four quarters is used instead. `current_year` is injectable for testing.
    """
    if is_commodity or income is None or income.empty:
        return None

    year_now = str(current_year or pd.Timestamp.now().year)
    annual = _annual_records(income)

    if year_now not in annual and quarterly_income is not None and not quarterly_income.empty:
        ttm = _ttm_record(quarterly_income)
        if ttm:
            annual[year_now] = ttm

    if not annual:
        return None

    labels = sorted(annual)[-5:]
    revenue = [annual[y]["revenue"] for y in labels]
    net_income = [annual[y]["net_income"] for y in labels]

    n_years = max(1, len(revenue) - 1)
    revenue_cagr = None
    if len(revenue) >= 2 and revenue[0] > 0 and revenue[-1] > 0:
        revenue_cagr = ((revenue[-1] / revenue[0]) ** (1 / n_years) - 1) * 100

    target_year = year_now if year_now in annual else labels[-1]
    return {
        "labels": labels,
        "revenue": revenue,
        "net_income": net_income,
        "revenue_cagr": revenue_cagr,
        "n_years": n_years,
        "target_year": target_year,
        "target_revenue": annual[target_year]["revenue"],
        "target_net_income": annual[target_year]["net_income"],
    }


# ----------------------------------------------------------------------
# Dividends
# ----------------------------------------------------------------------
def compute_dividend_metrics(info: dict, is_commodity: bool = False) -> dict | None:
    """Dividend rate, yield (%) and payout ratio (%) from Yahoo's profile info."""
    if is_commodity:
        return None
    rate = info.get("dividendRate")
    yield_val = info.get("dividendYield")
    payout = info.get("payoutRatio")
    return {
        "rate": rate if (rate is not None and pd.notna(rate)) else None,
        "yield_pct": yield_val * 100 if (yield_val is not None and pd.notna(yield_val)) else None,
        "payout_pct": payout * 100 if (payout is not None and pd.notna(payout)) else None,
    }


# ----------------------------------------------------------------------
# Leverage
# ----------------------------------------------------------------------
def compute_debt_metrics(
    balance: pd.DataFrame | None,
    income: pd.DataFrame | None,
    is_financial: bool = False,
    is_commodity: bool = False,
) -> dict | None:
    """Debt-to-equity and interest coverage for the latest fiscal year."""
    if is_commodity or is_financial:
        return None
    if balance is None or income is None or balance.empty or income.empty:
        return None

    metrics = {}

    try:
        year = sorted_columns(balance)[-1]
        equity = safe_get_metric(balance, ["Stockholders Equity", "Total Equity Gross Minority Interest"], year)
        debt = safe_get_metric(
            balance, ["Total Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"], year
        )
        if debt is not None and equity and equity > 0:
            metrics["debt_to_equity"] = debt / equity
    except (TypeError, ValueError, IndexError) as exc:
        logger.warning("Debt-to-equity unavailable: %s", exc)

    try:
        year = sorted_columns(income)[-1]
        ebit = safe_get_metric(income, ["EBIT", "Operating Income"], year)
        interest = safe_get_metric(income, ["Interest Expense", "Interest Expense Non Operating"], year)
        if ebit is not None and interest and abs(interest) > 0:
            metrics["interest_coverage"] = ebit / abs(interest)
    except (TypeError, ValueError, IndexError) as exc:
        logger.warning("Interest coverage unavailable: %s", exc)

    return metrics or None


# ----------------------------------------------------------------------
# Piotroski F-score
# ----------------------------------------------------------------------
def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    """numerator / denominator, or None if either is missing or the denominator is <= 0."""
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _piotroski_series(income, balance, cashflow, years) -> dict[str, list]:
    """Build the yearly series (oldest to newest) needed by the 9 criteria."""
    series = {k: [] for k in ("roa", "cfo", "debt", "current_ratio", "margin", "turnover", "shares")}
    for year in years:
        net_income = safe_get_metric(income, NET_INCOME_KEYS, year)
        assets = safe_get_metric(balance, ["Total Assets"], year)
        revenue = safe_get_metric(income, REVENUE_KEYS, year)

        series["roa"].append(_ratio(net_income, assets))
        series["cfo"].append(safe_get_metric(cashflow, OCF_KEYS, year))
        series["debt"].append(safe_get_metric(balance, LT_DEBT_KEYS, year) or 0.0)
        series["current_ratio"].append(
            _ratio(safe_get_metric(balance, ["Current Assets"], year),
                   safe_get_metric(balance, ["Current Liabilities"], year))
        )
        series["margin"].append(_ratio(safe_get_metric(income, ["Gross Profit"], year), revenue))
        series["turnover"].append(_ratio(revenue, assets))
        series["shares"].append(safe_get_metric(balance, SHARES_KEYS, year))
    return series


def compute_piotroski(
    income: pd.DataFrame | None,
    balance: pd.DataFrame | None,
    cashflow: pd.DataFrame | None,
    is_financial: bool = False,
    is_commodity: bool = False,
) -> dict | None:
    """Piotroski F-score over the last years available in all three statements.

    Returns {"score", "max_score", "criteria"} where criteria maps each
    test's label to True/False. A criterion is skipped when data is missing.
    """
    if is_financial or is_commodity:
        return None
    if any(df is None or df.empty for df in (income, balance, cashflow)):
        return None

    common = [y for y in income.columns if y in balance.columns and y in cashflow.columns]
    years = sorted(common, key=pd.to_datetime)[-4:]
    if len(years) < 2:
        return None

    raw = _piotroski_series(income, balance, cashflow, years)
    s = {k: [x for x in v if x is not None] for k, v in raw.items()}

    if len(s["roa"]) < 2 or len(s["cfo"]) < 2:
        return None

    net_income_last = safe_get_metric(income, ["Net Income"], years[-1])

    criteria: dict[str, bool] = {
        "Positive Return on Assets (ROA > 0)": s["roa"][-1] > 0,
        "Positive Operating Cash Flow (CFO > 0)": s["cfo"][-1] > 0,
        "Increasing Return on Assets (ROA)": s["roa"][-1] > 0 and s["roa"][-1] > s["roa"][-2],
    }
    if net_income_last is not None:
        criteria["Cash Quality (CFO > Net Income)"] = s["cfo"][-1] > net_income_last
    if len(s["debt"]) >= 2:
        criteria["Long-Term Debt Decreasing / Stable"] = s["debt"][-1] <= s["debt"][-2]
    if len(s["current_ratio"]) >= 2:
        criteria["Liquidity Increasing (Current Ratio)"] = s["current_ratio"][-1] > s["current_ratio"][-2]
    if len(s["shares"]) >= 2:
        criteria["No Share Dilution"] = s["shares"][-1] <= s["shares"][-2]
    if len(s["margin"]) >= 2:
        criteria["Gross Margin Increasing"] = s["margin"][-1] > s["margin"][-2]
    if len(s["turnover"]) >= 2:
        criteria["Asset Turnover Increasing"] = s["turnover"][-1] > s["turnover"][-2]

    score = sum(1 for passed in criteria.values() if passed)
    return {"score": score, "max_score": len(criteria), "criteria": criteria}# -*- coding: utf-8 -*-

