"""Tab rendering: Fundamental & Solvency research and Quantitative risk."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from market_analyzer.ui import charts
from market_analyzer.ui.styles import PALETTE
from market_analyzer.utils.formatting import format_financial_value


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _yoy_labels(values: list[float]) -> list[str]:
    """Year-over-year change as text, first entry being '-'."""
    labels = ["-"]
    for prev, curr in zip(values[:-1], values[1:]):
        if prev:
            change = (curr - prev) / abs(prev) * 100
            labels.append(f"{'+' if change > 0 else ''}{change:.1f}%")
        else:
            labels.append("N/A")
    return labels


def _statement_table(labels: list[str], values: list[float], title: str, sym: str) -> pd.DataFrame:
    return pd.DataFrame({
        "Fiscal Year": labels,
        title: [format_financial_value(v, sym) for v in values],
        "YoY": _yoy_labels(values),
    }).set_index("Fiscal Year")


def _fmt(value, template: str = "{:.2f}") -> str:
    return "N/A" if value is None or pd.isna(value) else template.format(value)


# ----------------------------------------------------------------------
# Fundamental tab
# ----------------------------------------------------------------------
def _render_growth(growth: dict | None, sym: str, currency_code: str) -> None:
    st.subheader("REVENUE & NET INCOME PERFORMANCE")
    if not growth:
        st.info("Insufficient accounting records to calculate multi-year growth trajectories.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.caption(f"REVENUE ({currency_code})")
        st.dataframe(
            _statement_table(growth["labels"], growth["revenue"], "Revenue", sym),
            use_container_width=True,
        )
    with col2:
        st.caption(f"NET INCOME ({currency_code})")
        st.dataframe(
            _statement_table(growth["labels"], growth["net_income"], "Net Income", sym),
            use_container_width=True,
        )

    if growth["revenue_cagr"] is not None and len(growth["revenue"]) > 1:
        cagr = round(growth["revenue_cagr"], 2)
        color = PALETTE["positive"] if cagr >= 0 else PALETTE["negative"]
        st.markdown(
            f"**{growth['n_years']}-Year Annual Growth Rate:** "
            f"<span style='color: {color}; font-family: monospace; font-weight: 600;'>{cagr:+.2f}%</span>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    st.caption(f"FINANCIAL PERFORMANCE — {growth['target_year']}")
    st.altair_chart(
        charts.revenue_net_income_chart(growth["target_revenue"], growth["target_net_income"], sym),
        use_container_width=True,
    )


def _render_balance_sheet(debt_metrics, piotroski_result, is_financial: bool) -> None:
    st.subheader("BALANCE SHEET & ACCOUNTING QUALITY")
    if is_financial:
        st.info(
            "Debt-to-Equity, Interest Coverage, and Piotroski F-Score are neutralized "
            "for Financial Services due to deposit capital structures."
        )
        return

    col1, col2 = st.columns(2)
    if debt_metrics:
        dte = debt_metrics.get("debt_to_equity")
        cov = debt_metrics.get("interest_coverage")
        if dte is not None:
            col1.metric("DEBT / EQUITY", f"{dte:.2f}")
        if cov is not None:
            col2.metric("INTEREST COVERAGE", f"{cov:.2f}x")
        if dte is not None and cov is not None:
            debt_msg = (
                f"High leverage (Debt/Equity {dte:.2f}x)."
                if dte > 1.5
                else f"Conservative leverage (Debt/Equity {dte:.2f}x)."
            )
            cov_msg = (
                f"Strong operating income ({cov:.1f}x interest coverage) safely covers debt service."
                if cov >= 3.0
                else f"Tight interest coverage ({cov:.1f}x) requires careful cash monitoring."
            )
            st.caption(f"{debt_msg} {cov_msg}")
    else:
        st.info("Solvency and leverage ratios are unavailable for this security.")

    if piotroski_result:
        st.write("")
        st.metric("PIOTROSKI F-SCORE", f"{piotroski_result['score']} / {piotroski_result['max_score']}")
        st.markdown(
            "<p style='font-size: 0.85rem; font-weight: 700; color: #CBD5E1; text-transform: uppercase; "
            "margin-top: 1rem; margin-bottom: 0.5rem;'>Piotroski Criteria Breakdown</p>",
            unsafe_allow_html=True,
        )
        cols = st.columns(3)
        for i, (label, passed) in enumerate(piotroski_result["criteria"].items()):
            color, text = (PALETTE["positive"], "[PASS]") if passed else (PALETTE["negative"], "[FAIL]")
            with cols[i % 3]:
                st.markdown(
                    f"**{label}**: <span style='color: {color}; font-family: monospace; "
                    f"font-weight: 600;'>{text}</span>",
                    unsafe_allow_html=True,
                )


def _render_valuation(valuation, fcf, analyst_view, sym: str) -> None:
    st.subheader("VALUATION & MARKET VIEW")
    val_col, rec_col = st.columns(2)

    with val_col:
        if valuation and valuation.get("is_loss_making"):
            st.warning("Unprofitable: Current net income is negative; trailing P/E is not meaningful.")
        elif valuation and valuation.get("current_pe"):
            premium = valuation.get("premium_pct")
            st.metric(
                "CURRENT P/E VS 5Y AVG",
                round(valuation["current_pe"], 2),
                f"{premium:.1f}% vs 5Y avg ({valuation['avg_pe']:.2f})" if premium is not None else None,
                delta_color="inverse",
            )
        else:
            st.info("Insufficient historical records to contextualize the P/E multiple.")

        if fcf:
            st.write("")
            st.metric("FREE CASH FLOW YIELD", f"{fcf['yield_pct']:.2f}%")

    with rec_col:
        if not analyst_view:
            st.info("No consensus analyst targets available for this asset.")
            return
        upside = round(analyst_view["upside_pct"], 1)
        st.metric(
            "ANALYST CONSENSUS TARGET",
            f"{analyst_view['target_mean']:.2f} {sym}",
            f"{'+' if upside > 0 else ''}{upside}%",
        )
        if analyst_view["distribution"]:
            st.altair_chart(charts.analyst_chart(analyst_view["distribution"]), use_container_width=True)
            c = analyst_view["counts"]
            st.caption(
                f"External Wall Street aggregate: Buy {c['buy']} · Hold {c['hold']} · "
                f"Sell {c['sell']} (total: {c['total']})."
            )


def render_fundamental_tab(
    *,
    is_commodity: bool,
    is_financial: bool,
    growth: dict | None,
    debt_metrics: dict | None,
    piotroski_result: dict | None,
    valuation: dict | None,
    fcf: dict | None,
    analyst_view: dict | None,
    sym: str,
    currency_code: str,
) -> None:
    """Render the Fundamental & Solvency research tab."""
    if is_commodity:
        st.info("Commodity futures contracts do not possess financial statements. Please refer to the quantitative risk tab.")
        return
    _render_growth(growth, sym, currency_code)
    st.divider()
    _render_balance_sheet(debt_metrics, piotroski_result, is_financial)
    st.divider()
    _render_valuation(valuation, fcf, analyst_view, sym)


# ----------------------------------------------------------------------
# Quantitative tab
# ----------------------------------------------------------------------
def _render_sensitivity(quant: dict, benchmark_name: str | None, show_benchmark: bool) -> None:
    st.subheader("PERFORMANCE & MARKET SENSITIVITY")
    if show_benchmark:
        b1, b2, b3, b4 = st.columns(4)
        b1.metric(f"BETA ({benchmark_name})", _fmt(quant["beta"]))
        b2.metric("JENSEN'S ALPHA (ANN.)", _fmt(quant["alpha"], "{:.2f}%"))
        b3.metric("R-SQUARED (CORR.)", _fmt(quant["r_squared"]))
        b4.metric("SORTINO RATIO", _fmt(quant["sortino_ratio"]))
        if quant.get("benchmark_error"):
            st.caption(f"Benchmark notice: {quant['benchmark_error']}")
    else:
        b1, b2, b3 = st.columns(3)
        b1.metric("ANNUALIZED VOLATILITY", f"{quant['annualized_volatility']:.2f}%")
        b2.metric("SHARPE RATIO", _fmt(quant["sharpe_ratio"]))
        b3.metric("SORTINO RATIO", _fmt(quant["sortino_ratio"]))


def _render_var_tables(quant: dict) -> None:
    st.subheader("VALUE-AT-RISK & EXPECTED SHORTFALL")
    col1, col2 = st.columns(2)
    with col1:
        var_df = pd.DataFrame({
            "Horizon & Confidence": [
                "95% Confidence (1-Day)",
                "99% Confidence (1-Day)",
                "95% Confidence (10-Day, √10 scaling)",
            ],
            "Historical VaR": [f"-{quant['hist_var_95_1d']:.2f}%", f"-{quant['hist_var_99_1d']:.2f}%", "-"],
            "Parametric VaR": [
                f"-{quant['param_var_95_1d']:.2f}%",
                f"-{quant['param_var_99_1d']:.2f}%",
                f"-{quant['param_var_95_10d']:.2f}%",
            ],
        }).set_index("Horizon & Confidence")
        st.dataframe(var_df, use_container_width=True)
    with col2:
        cvar_df = pd.DataFrame({
            "Confidence Level": ["95% Confidence Level", "99% Confidence Level"],
            "Expected Shortfall (CVaR)": [
                f"-{quant['hist_cvar_95_1d']:.2f}%",
                f"-{quant['hist_cvar_99_1d']:.2f}%",
            ],
            "Modified VaR (Cornish-Fisher)": [f"-{quant['cf_mod_var_95_1d']:.2f}%", "-"],
        }).set_index("Confidence Level")
        st.dataframe(cvar_df, use_container_width=True)


def render_quant_tab(
    *,
    quant: dict | None,
    benchmark_name: str | None,
    is_commodity: bool,
    risk_free_rate: float,
    currency_code: str,
) -> None:
    """Render the Quantitative risk & market dynamics tab."""
    if not quant:
        st.subheader("PERFORMANCE & MARKET SENSITIVITY")
        st.info("Insufficient quotation history to compute quantitative risk models.")
        return

    _render_sensitivity(quant, benchmark_name, show_benchmark=(not is_commodity and bool(benchmark_name)))
    st.divider()

    st.subheader("RETURN DISTRIBUTION & TAIL RISK")
    st.altair_chart(
        charts.return_distribution_chart(
            quant["returns_series"] * 100,
            -quant["hist_var_95_1d"],
            -quant["hist_cvar_95_1d"],
        ),
        use_container_width=True,
    )
    st.divider()

    _render_var_tables(quant)
    st.caption(
        "Parametric VaR assumes normal returns and understates tail risk. "
        "Cornish-Fisher adjusts for skewness and kurtosis to capture extreme market shocks."
    )
    st.caption(
        f"Statistical Moments: Skewness: `{quant['skewness']:.2f}` | "
        f"Excess Kurtosis: `{quant['kurtosis']:.2f}` | "
        f"Applied Risk-Free Rate: `{risk_free_rate * 100:.2f}%` ({currency_code})."
    )