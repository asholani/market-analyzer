"""Pure formatting and extraction helpers (no Streamlit, no network)."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from market_analyzer.config import CURRENCY_SYMBOLS


def get_currency_symbol(curr_code: str | None) -> str:
    """Return the display symbol for an ISO currency code (falls back to the code)."""
    return CURRENCY_SYMBOLS.get(str(curr_code).upper(), curr_code or "$")


def safe_str(value, default: str = "N/A") -> str:
    """Convert a value to str, returning `default` for None or NaN."""
    if value is None:
        return default
    try:
        if isinstance(value, float) and pd.isna(value):
            return default
    except TypeError:
        pass
    return str(value)


def safe_get_metric(df: pd.DataFrame | None, keys: Iterable[str], col) -> float | None:
    """Return the first non-null value found in `df` for any row label in `keys`.

    Yahoo Finance renames line items between companies (e.g. "Total Revenue"
    vs "Operating Revenue"), so several candidate labels are tried in order.
    """
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            try:
                val = df.loc[key, col]
                if pd.notna(val):
                    return float(val)
            except (KeyError, TypeError, ValueError):
                continue
    return None


def format_financial_value(value: float | None, currency_sym: str = "$") -> str:
    """Format a number as a compact currency string (K / M / B)."""
    if value is None or pd.isna(value):
        return "N/A"
    value = float(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000_000:
        return f"{sign}{currency_sym}{value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{sign}{currency_sym}{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{sign}{currency_sym}{value / 1_000:.1f}K"
    return f"{sign}{currency_sym}{value:.0f}"


def build_profile_table(info: dict, is_commodity: bool = False) -> pd.DataFrame:
    """Build the Attribute/Value factsheet table shown in the app."""
    if is_commodity:
        data = [
            ("Asset Class", "Commodity / Futures Contract"),
            ("Exchange", safe_str(info.get("exchange"))),
            ("Market", safe_str(info.get("market"))),
            ("Quote Type", safe_str(info.get("quoteType"), default="FUTURE")),
            ("Settlement Currency", (info.get("currency") or "USD").upper()),
            ("Underlying Instrument", safe_str(info.get("underlyingSymbol") or info.get("shortName"))),
        ]
    else:
        hq_parts = [p for p in (info.get("city"), info.get("state"), info.get("country")) if p]
        hq = ", ".join(hq_parts) if hq_parts else "N/A"

        employees = info.get("fullTimeEmployees")
        emp_str = f"{employees:,}" if (employees and pd.notna(employees)) else "N/A"

        ceo_name = "N/A"
        officers = info.get("companyOfficers") or []
        if isinstance(officers, list) and officers:
            for off in officers:
                title = str(off.get("title", "")).lower()
                if "chief executive officer" in title or "ceo" in title or "president" in title:
                    ceo_name = safe_str(off.get("name"))
                    break
            if ceo_name == "N/A" and "name" in officers[0]:
                ceo_name = safe_str(officers[0].get("name"))

        data = [
            ("Sector", safe_str(info.get("sector"))),
            ("Industry", safe_str(info.get("industry"))),
            ("Headquarters", hq),
            ("Full-Time Employees", emp_str),
            ("Key Executive (CEO)", ceo_name),
            ("Website", safe_str(info.get("website"))),
        ]

    return pd.DataFrame(data, columns=["Attribute", "Value"])