"""Build the searchable universe of assets (indices from Wikipedia + static catalogs)."""

from __future__ import annotations

import logging
import re
from io import StringIO

import pandas as pd
import requests

from market_analyzer.config import ASIAN_FLAGSHIPS, COMMODITIES_CATALOG, HEADERS

logger = logging.getLogger(__name__)

EMPTY_TABLE = pd.DataFrame(columns=["ticker", "name"])

INDEX_SOURCES = {
    "nasdaq100": {
        "url": "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies",
        "tickers": ["Ticker", "Symbol", "Ticker symbol"],
        "names": ["Company", "Company name", "Name"],
        "suffix": None,
    },
    "dow_jones": {
        "url": "https://en.wikipedia.org/wiki/List_of_Dow_Jones_Industrial_Average_companies",
        "tickers": ["Symbol", "Ticker", "Ticker symbol"],
        "names": ["Company", "Company name", "Name"],
        "suffix": None,
    },
    "cac40": {
        "url": "https://en.wikipedia.org/wiki/CAC_40",
        "tickers": ["Ticker", "Symbol", "Ticker symbol"],
        "names": ["Company", "Company name", "Name"],
        "suffix": ".PA",
    },
    "dax": {
        "url": "https://en.wikipedia.org/wiki/DAX",
        "tickers": ["Ticker symbol", "Ticker", "Symbol"],
        "names": ["Company", "Company name", "Name"],
        "suffix": ".DE",
    },
}


def _fetch_tables(url: str) -> list[pd.DataFrame]:
    """Download a web page and return all the HTML tables it contains."""
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return pd.read_html(StringIO(response.text))


def _flatten_columns(table: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex column headers into plain strings."""
    if isinstance(table.columns, pd.MultiIndex):
        table.columns = [
            " ".join(str(x) for x in col if str(x) != "nan").strip()
            for col in table.columns
        ]
    return table


def _find_table(url: str, ticker_candidates: list[str], name_candidates: list[str]) -> pd.DataFrame:
    """Return a (ticker, name) table from the first page table that has matching columns."""
    try:
        tables = _fetch_tables(url)
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Could not load constituents from %s: %s", url, exc)
        return EMPTY_TABLE.copy()

    for table in tables:
        table = _flatten_columns(table)
        normalized = {str(c).strip().lower(): c for c in table.columns}
        ticker_col = next((normalized[c.lower()] for c in ticker_candidates if c.lower() in normalized), None)
        name_col = next((normalized[c.lower()] for c in name_candidates if c.lower() in normalized), None)

        if ticker_col is not None and name_col is not None:
            result = table[[ticker_col, name_col]].copy()
            result.columns = ["ticker", "name"]
            return result.dropna(subset=["ticker", "name"])

    logger.warning("No table with the expected columns found at %s", url)
    return EMPTY_TABLE.copy()


def clean_ticker(ticker: str, suffix: str | None = None) -> str:
    """Normalize a ticker to Yahoo Finance format (e.g. 'BRK.B' -> 'BRK-B', 'AIR' -> 'AIR.PA')."""
    ticker = str(ticker).strip().upper()
    ticker = re.sub(r"\[.*?\]", "", ticker).strip()
    ticker = ticker.replace(" ", "").replace(".", "-")
    if suffix:
        suffix_clean = suffix.replace(".", "").upper()
        if ticker.endswith(f"-{suffix_clean}"):
            ticker = ticker.replace(f"-{suffix_clean}", suffix)
        elif not ticker.endswith(suffix):
            ticker = f"{ticker}{suffix}"
    return ticker


def _build_index_dict(source: dict) -> dict[str, str]:
    """Return {ticker: company name} for one index."""
    table = _find_table(source["url"], source["tickers"], source["names"])
    companies = {}
    for _, row in table.iterrows():
        ticker = clean_ticker(row["ticker"], source["suffix"])
        name = re.sub(r"\[.*?\]", "", str(row["name"])).strip()
        if ticker and ticker.lower() != "nan":
            companies[ticker] = name
    return companies


def load_market_universe() -> dict[str, str]:
    """Return {ticker: name} for commodities, Asian flagships and major indices.

    Static catalogs take priority; index constituents only fill the gaps.
    Network failures are logged and the corresponding index is skipped.
    """
    universe: dict[str, str] = {}
    universe.update(COMMODITIES_CATALOG)
    universe.update(ASIAN_FLAGSHIPS)
    for source in INDEX_SOURCES.values():
        constituents = _build_index_dict(source)
        universe.update({k: v for k, v in constituents.items() if k not in universe})
    return universe# -*- coding: utf-8 -*-

