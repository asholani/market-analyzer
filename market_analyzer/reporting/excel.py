"""Excel report generation (openpyxl engine)."""

from __future__ import annotations

from io import BytesIO

import pandas as pd


def _fmt(value, template: str = "{:.2f}", default: str = "N/A") -> str:
    """Format a number with `template`, or return `default` if it is None/NaN."""
    if value is None or pd.isna(value):
        return default
    return template.format(value)


def _overview_sheet(name, ticker, sector, industry, price, sym, is_commodity) -> pd.DataFrame:
    return pd.DataFrame({
        "Metric": ["Asset Name", "Ticker", "Sector / Class", "Industry", "Current Price"],
        "Value": [
            name,
            ticker.upper(),
            sector or ("Commodity" if is_commodity else "N/A"),
            industry or "N/A",
            f"{price:.2f} {sym}" if price is not None else "N/A",
        ],
    })


def _valuation_sheet(valuation, fcf, div_metrics, debt_metrics, is_financial) -> pd.DataFrame:
    rows = []
    if valuation:
        rows += [
            {"Indicator": "Current P/E (price / last annual EPS)", "Value": _fmt(valuation.get("current_pe"))},
            {"Indicator": "5Y Avg Historical P/E", "Value": _fmt(valuation.get("avg_pe"))},
            {"Indicator": "Premium / Discount vs History (%)", "Value": _fmt(valuation.get("premium_pct"), "{:.1f}%")},
            {"Indicator": "Status", "Value": "Unprofitable" if valuation.get("is_loss_making") else "Profitable"},
        ]
    if fcf:
        rows.append({"Indicator": "Free Cash Flow Yield (%)", "Value": _fmt(fcf["yield_pct"], "{:.2f}%")})
    if div_metrics:
        rows += [
            {"Indicator": "Dividend Yield (%)", "Value": _fmt(div_metrics.get("yield_pct"), "{:.2f}%")},
            {"Indicator": "Payout Ratio (%)", "Value": _fmt(div_metrics.get("payout_pct"), "{:.1f}%")},
        ]
    if not is_financial and debt_metrics:
        if "debt_to_equity" in debt_metrics:
            rows.append({"Indicator": "Debt-to-Equity", "Value": _fmt(debt_metrics["debt_to_equity"])})
        if "interest_coverage" in debt_metrics:
            rows.append({"Indicator": "Interest Coverage (x)", "Value": _fmt(debt_metrics["interest_coverage"], "{:.2f}x")})
    return pd.DataFrame(rows, columns=["Indicator", "Value"])


def _piotroski_sheet(piotroski_result) -> pd.DataFrame:
    return pd.DataFrame([
        {"Criteria": label, "Status": "PASS" if passed else "FAIL"}
        for label, passed in piotroski_result["criteria"].items()
    ])


def _risk_sheet(quant, benchmark_name, is_commodity) -> pd.DataFrame:
    rows = [
        ("Annualized Volatility (252d)", _fmt(quant["annualized_volatility"], "{:.2f}%")),
        ("Maximum Drawdown (5Y)", _fmt(quant["max_drawdown"], "{:.2f}%")),
        ("Sharpe Ratio", _fmt(quant["sharpe_ratio"])),
        ("Sortino Ratio", _fmt(quant["sortino_ratio"])),
        ("Daily Historical VaR (95%)", _fmt(quant["hist_var_95_1d"], "-{:.2f}%")),
        ("Daily Historical VaR (99%)", _fmt(quant["hist_var_99_1d"], "-{:.2f}%")),
        ("Daily Expected Shortfall / CVaR (95%)", _fmt(quant["hist_cvar_95_1d"], "-{:.2f}%")),
        ("Daily Expected Shortfall / CVaR (99%)", _fmt(quant["hist_cvar_99_1d"], "-{:.2f}%")),
        ("10-Day Parametric VaR (95%)", _fmt(quant["param_var_95_10d"], "-{:.2f}%")),
        ("Cornish-Fisher Modified VaR (95% 1d)", _fmt(quant["cf_mod_var_95_1d"], "-{:.2f}%")),
    ]
    if not is_commodity and benchmark_name:
        rows += [
            ("Benchmark Index", benchmark_name),
            ("Market Beta", _fmt(quant.get("beta"))),
            ("Annualized Jensen's Alpha", _fmt(quant.get("alpha"), "{:.2f}%")),
            ("R-squared vs Benchmark", _fmt(quant.get("r_squared"))),
        ]
    rows += [
        ("Skewness", _fmt(quant["skewness"])),
        ("Excess Kurtosis", _fmt(quant["kurtosis"])),
    ]
    return pd.DataFrame(rows, columns=["Risk Metric", "Value"])


def generate_excel_report(
    name: str,
    ticker: str,
    sector: str | None,
    industry: str | None,
    price: float | None,
    sym: str,
    valuation: dict | None,
    fcf: dict | None,
    div_metrics: dict | None,
    piotroski_result: dict | None,
    debt_metrics: dict | None,
    quant_metrics: dict | None,
    benchmark_name: str | None,
    is_financial: bool,
    is_commodity: bool,
) -> bytes:
    """Build the multi-sheet Excel report and return it as bytes (ready for a download button)."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        _overview_sheet(name, ticker, sector, industry, price, sym, is_commodity).to_excel(
            writer, sheet_name="Overview", index=False
        )
        if not is_commodity:
            _valuation_sheet(valuation, fcf, div_metrics, debt_metrics, is_financial).to_excel(
                writer, sheet_name="Valuation & Debt", index=False
            )
            if piotroski_result and not is_financial:
                _piotroski_sheet(piotroski_result).to_excel(
                    writer, sheet_name="Piotroski Details", index=False
                )
        if quant_metrics:
            _risk_sheet(quant_metrics, benchmark_name, is_commodity).to_excel(
                writer, sheet_name="Quantitative Risk", index=False
            )
    return output.getvalue()

