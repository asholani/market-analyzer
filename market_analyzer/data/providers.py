"""Network access layer: Yahoo Finance prices/financials and Google News headlines."""

from __future__ import annotations

import logging
from urllib.parse import quote

import feedparser
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# timeframe label -> arguments for yfinance's Ticker.history()
TIMEFRAMES = {
    "1D": {"period": "1d", "interval": "5m"},
    "1W": {"period": "5d", "interval": "15m"},
    "1M": {"period": "1mo"},
    "3M": {"period": "3mo"},
    "1Y": {"period": "1y"},
    "5Y": {"period": "5y"},
    "10Y": {"period": "10y"},
}


def get_stock_data(ticker: str):
    """Fetch profile info, 10-year price history, financial statements and analyst recommendations.

    Returns (info, history_10y, income, quarterly_income, balance, cashflow, recs).
    """
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    history_10y = stock.history(period="10y")
    income = stock.financials
    quarterly_income = stock.quarterly_financials
    balance = stock.balance_sheet
    cashflow = stock.cashflow
    try:
        recs = stock.recommendations
    except Exception as exc:  # yfinance raises assorted errors depending on the asset
        logger.warning("No recommendations for %s: %s", ticker, exc)
        recs = None
    return info, history_10y, income, quarterly_income, balance, cashflow, recs


def get_price_history(ticker: str, timeframe: str) -> pd.DataFrame:
    """Price history for a timeframe label ('1D', '1W', '1M', '3M', '1Y', '5Y', '10Y').

    Works for both stocks and benchmark indices. Unknown labels fall back to 10Y.
    """
    params = TIMEFRAMES.get(timeframe, TIMEFRAMES["10Y"])
    df = yf.Ticker(ticker).history(**params)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.dropna(subset=["Close"])


def get_close_history(ticker: str, period: str = "10y") -> pd.Series:
    """Daily closing prices only, as a Series (empty if unavailable)."""
    df = yf.Ticker(ticker).history(period=period)
    if df is None or df.empty or "Close" not in df:
        return pd.Series(dtype=float)
    return df["Close"].dropna()


def get_news(asset_name: str, limit: int = 5) -> list[dict]:
    """Latest Google News headlines about an asset."""
    query = quote(f"{asset_name} finance")
    url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"
    feed = feedparser.parse(url)
    news = []
    for entry in feed.entries[:limit]:
        news.append({
            "title": entry.title,
            "source": entry.source.title if "source" in entry else "Unknown",
            "published": entry.published,
            "link": entry.link,
        })
    return news# -*- coding: utf-8 -*-

