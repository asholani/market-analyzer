"""Market Analyzer: Streamlit entry point.

Combines fundamental analysis (growth, Piotroski, leverage, valuation, analyst
consensus) with quantitative market-risk analysis (volatility, VaR, CVaR,
Cornish-Fisher, CAPM beta/alpha, Sharpe/Sortino).

Run with:  python -m streamlit run app.py
"""

from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

from market_analyzer.analysis import fundamentals
from market_analyzer.analysis import valuation as val
from market_analyzer.analysis.risk import compute_risk_metrics, resolve_benchmark_ticker
from market_analyzer.config import DEFAULT_RF_FALLBACK, DEFAULT_RF_RATES
from market_analyzer.data import providers
from market_analyzer.data.universe import load_market_universe
from market_analyzer.reporting.excel import generate_excel_report
from market_analyzer.ui import charts
from market_analyzer.ui.styles import apply_theme
from market_analyzer.ui.tabs import render_fundamental_tab, render_quant_tab
from market_analyzer.utils.formatting import (
    build_profile_table,
    get_currency_symbol,
    safe_get_metric,
    safe_str,
)

logging.basicConfig(level=logging.WARNING)

st.set_page_config(page_title="Market Analyzer", layout="wide")
apply_theme()

TIMEFRAMES = ["1D", "1W", "1M", "3M", "1Y", "5Y", "10Y"]


# ----------------------------------------------------------------------
# Cached data access (caching lives here, not in the data/analysis modules)
# ----------------------------------------------------------------------
@st.cache_data(ttl=86400)
def cached_universe() -> dict[str, str]:
    return load_market_universe()


@st.cache_data(ttl=3600)
def cached_stock_data(ticker: str):
    return providers.get_stock_data(ticker)


@st.cache_data(ttl=3600)
def cached_price_history(ticker: str, timeframe: str) -> pd.DataFrame:
    return providers.get_price_history(ticker, timeframe)


@st.cache_data(ttl=3600)
def cached_risk(ticker: str, bench_symbol: str | None, risk_free_rate: float):
    close = providers.get_close_history(ticker)
    bench_close = providers.get_close_history(bench_symbol) if bench_symbol else None
    return compute_risk_metrics(close, bench_close, risk_free_rate)


@st.cache_data(ttl=1800)
def cached_news(asset_name: str) -> list[dict]:
    return providers.get_news(asset_name)


# ----------------------------------------------------------------------
# KPI strip
# ----------------------------------------------------------------------
def _pe_metric(col, income, history_ytd, price, start_price) -> None:
    cols = fundamentals.sorted_columns(income)
    eps_t = safe_get_metric(income, val.EPS_KEYS, cols[-1])
    eps_t1 = safe_get_metric(income, val.EPS_KEYS, cols[-2]) if len(cols) >= 2 else None

    if eps_t is None:
        col.metric("P/E MULTIPLE", "N/A")
    elif eps_t <= 0:
        col.metric("P/E MULTIPLE", "N/M", "Loss-making")
    elif price:
        pe_now = price / eps_t
        change = None
        if eps_t1 and eps_t1 > 0 and start_price is not None:
            pe_start = start_price / eps_t1
            change = (pe_now - pe_start) / pe_start * 100
        col.metric("P/E MULTIPLE", round(pe_now, 2), f"{change:+.2f}% (YTD)" if change is not None else None)
    else:
        col.metric("P/E MULTIPLE", "N/A")


def _roe_metric(col, income, balance) -> None:
    inc_cols = fundamentals.sorted_columns(income)
    bal_cols = fundamentals.sorted_columns(balance)
    ni_t = safe_get_metric(income, ["Net Income"], inc_cols[-1])
    eq_t = safe_get_metric(balance, ["Stockholders Equity"], bal_cols[-1])
    if ni_t is None or not eq_t or eq_t <= 0:
        col.metric("RETURN ON EQUITY", "N/A")
        return

    roe = ni_t / eq_t * 100
    change = None
    if len(inc_cols) >= 2 and len(bal_cols) >= 2:
        ni_p = safe_get_metric(income, ["Net Income"], inc_cols[-2])
        eq_p = safe_get_metric(balance, ["Stockholders Equity"], bal_cols[-2])
        if ni_p is not None and eq_p and eq_p > 0:
            change = roe - ni_p / eq_p * 100
    col.metric("RETURN ON EQUITY", f"{roe:.2f}%", f"{change:+.2f} pts" if change is not None else None)


def render_kpis(price, history, income, balance, div_metrics, quant, sym, is_commodity) -> None:
    col1, col2, col3, col4 = st.columns(4)
    year = str(pd.Timestamp.now().year)
    history_ytd = history[history.index >= f"{year}-01-01"]

    start_price = None
    if price and not history_ytd.empty:
        start_price = float(history_ytd["Close"].iloc[0])
        change = (price - start_price) / start_price * 100
        col1.metric("LAST CLOSE", f"{price:.2f} {sym}", f"{change:+.2f}% (YTD)")
    elif price:
        col1.metric("LAST CLOSE", f"{price:.2f} {sym}")

    if is_commodity:
        if quant:
            col2.metric("ANNUALIZED VOLATILITY", f"{quant['annualized_volatility']:.1f}%")
            col3.metric("5Y MAX DRAWDOWN", f"{quant['max_drawdown']:.1f}%")
            sharpe = quant["sharpe_ratio"]
            col4.metric("SHARPE RATIO", f"{sharpe:.2f}" if sharpe is not None else "N/A")
        return

    has_statements = income is not None and not income.empty
    if has_statements:
        _pe_metric(col2, income, history_ytd, price, start_price)
    else:
        col2.metric("P/E MULTIPLE", "N/A")

    if has_statements and balance is not None and not balance.empty:
        _roe_metric(col3, income, balance)
    else:
        col3.metric("RETURN ON EQUITY", "N/A")

    if div_metrics and div_metrics["yield_pct"] is not None:
        payout = f"Payout: {div_metrics['payout_pct']:.0f}%" if div_metrics["payout_pct"] else None
        col4.metric("DIVIDEND YIELD", f"{div_metrics['yield_pct']:.2f}%", payout)
    else:
        col4.metric("DIVIDEND YIELD", "0.00%", "No regular payout")


# ----------------------------------------------------------------------
# Price chart section
# ----------------------------------------------------------------------
def render_price_section(ticker, sym, bench_symbol, bench_name) -> None:
    st.write("")
    if bench_symbol:
        tf_col, toggle_col = st.columns([3, 1])
        with tf_col:
            timeframe = st.pills("Horizon", TIMEFRAMES, default="1Y", label_visibility="collapsed")
        with toggle_col:
            compare = st.checkbox(f"Compare with {bench_name}", value=False)
    else:
        timeframe = st.pills("Horizon", TIMEFRAMES, default="1Y", label_visibility="collapsed")
        compare = False
    timeframe = timeframe or "1Y"  # pills return None if the user deselects everything

    history = cached_price_history(ticker, timeframe)
    if history is None or len(history) < 2 or "Close" not in history:
        st.warning(f"No price history available for timeframe '{timeframe}'.")
        return

    closes = history["Close"].dropna()
    p_start, p_end = float(closes.iloc[0]), float(closes.iloc[-1])
    period_return = (p_end - p_start) / p_start * 100

    metric_col, _ = st.columns([1, 4])
    with metric_col:
        st.metric(f"{timeframe} PERFORMANCE", f"{p_end:.2f} {sym}", f"{period_return:+.2f}%")

    bench_history = cached_price_history(bench_symbol, timeframe) if (compare and bench_symbol) else None
    st.altair_chart(
        charts.price_chart(history, ticker, sym, bench_history, bench_name),
        use_container_width=True,
    )


# ----------------------------------------------------------------------
# Main page
# ----------------------------------------------------------------------
st.markdown(
    "<h1 style='text-align: center; margin-bottom: 1.5rem;'>MARKET ANALYZER</h1>",
    unsafe_allow_html=True,
)

universe = cached_universe()
search_options = [f"{t} — {n}" for t, n in universe.items()]
default_index = next((i for i, opt in enumerate(search_options) if opt.startswith("AAPL —")), 0)

_, search_col, _ = st.columns([1, 2, 1])
with search_col:
    selected_asset = st.selectbox(
        "Search Asset",
        options=search_options,
        index=default_index,
        placeholder="Type a ticker or asset name...",
        label_visibility="collapsed",
    )
ticker = selected_asset.split(" — ")[0] if selected_asset else "AAPL"

try:
    info, history_10y, income, quarterly_income, balance, cashflow, recs_df = cached_stock_data(ticker)
except Exception as exc:  # network / yfinance errors vary widely; show them to the user
    st.error(f"Unable to retrieve market data for '{ticker}'. Please check the symbol.")
    st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
    st.stop()

if history_10y is None or history_10y.empty:
    st.error(f"No price history returned for '{ticker}'.")
    st.stop()

name = info.get("longName") or info.get("shortName") or universe.get(ticker, ticker)
sector = info.get("sector")
industry = info.get("industry")
price = info.get("currentPrice") or info.get("regularMarketPrice")
currency_code = (info.get("currency") or "USD").upper()
sym = get_currency_symbol(currency_code)

is_commodity = ticker.endswith("=F") or info.get("quoteType") == "FUTURE"
is_financial = sector == "Financial Services"
bench_symbol, bench_name = resolve_benchmark_ticker(ticker)

with st.sidebar:
    st.subheader("MODEL PARAMETERS")
    rf_rate = st.slider(
        f"Risk-Free Rate (Rf) [{currency_code}]",
        min_value=0.0,
        max_value=0.08,
        value=float(DEFAULT_RF_RATES.get(currency_code, DEFAULT_RF_FALLBACK)),
        step=0.001,
        format="%.3f",
        help="Short-term sovereign reference rate (€STR, T-Bills, etc.).",
    )

profile_title = "CONTRACT SPECIFICATIONS" if is_commodity else "CORPORATE FACTSHEET"
with st.expander(profile_title, expanded=False):
    st.dataframe(build_profile_table(info, is_commodity), hide_index=True, use_container_width=True)

st.divider()

# ---- Analysis ----
growth = fundamentals.compute_growth_trends(income, quarterly_income, is_commodity)
div_metrics = fundamentals.compute_dividend_metrics(info, is_commodity)
debt_metrics = fundamentals.compute_debt_metrics(balance, income, is_financial, is_commodity)
piotroski_result = fundamentals.compute_piotroski(income, balance, cashflow, is_financial, is_commodity)
valuation_ctx = val.compute_valuation_context(history_10y, income, price, is_commodity)
fcf = val.compute_fcf_yield(cashflow, info.get("marketCap"), is_commodity)
analyst_view = val.get_analyst_view(info, recs_df, price, is_commodity)
quant = cached_risk(ticker, bench_symbol, rf_rate)

# ---- Header and Excel export ----
head_col, export_col = st.columns([3, 1])
with head_col:
    st.subheader(f"{name.upper()} ({ticker.upper()})")
    class_label = "Commodity Futures" if is_commodity else f"{safe_str(sector)} • {safe_str(industry)}"
    st.caption(f"{class_label} • Base Currency: {currency_code} ({sym})")
with export_col:
    try:
        excel_bytes = generate_excel_report(
            name, ticker, sector, industry, price, sym,
            valuation_ctx, fcf, div_metrics, piotroski_result, debt_metrics,
            quant, bench_name, is_financial, is_commodity,
        )
        st.download_button(
            label="DOWNLOAD EXCEL REPORT",
            data=excel_bytes,
            file_name=f"{ticker.upper()}_analysis_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except ImportError:
        st.caption("Excel export unavailable: please install 'openpyxl'.")

st.write("")
render_kpis(price, history_10y, income, balance, div_metrics, quant, sym, is_commodity)
render_price_section(ticker, sym, bench_symbol, bench_name)

st.divider()

# ---- Tabs ----
tab_fund, tab_quant = st.tabs(["FUNDAMENTAL & SOLVENCY RESEARCH", "QUANTITATIVE RISK & MARKET DYNAMICS"])
with tab_fund:
    render_fundamental_tab(
        is_commodity=is_commodity,
        is_financial=is_financial,
        growth=growth,
        debt_metrics=debt_metrics,
        piotroski_result=piotroski_result,
        valuation=valuation_ctx,
        fcf=fcf,
        analyst_view=analyst_view,
        sym=sym,
        currency_code=currency_code,
    )
with tab_quant:
    render_quant_tab(
        quant=quant,
        benchmark_name=bench_name,
        is_commodity=is_commodity,
        risk_free_rate=rf_rate,
        currency_code=currency_code,
    )

st.divider()

with st.expander("NEWS"):
    news_items = cached_news(name)
    if news_items:
        for item in news_items:
            st.markdown(f"**{item['title']}**")
            st.caption(f"{item['source']} · {item['published']}")
            st.markdown(f"[Source Article]({item['link']})")
            st.divider()
    else:
        st.info("No recent news found.")

st.caption("Institutional research & risk management platform — not investment advice.")