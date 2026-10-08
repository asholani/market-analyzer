from io import BytesIO

import pandas as pd

from market_analyzer.reporting.excel import generate_excel_report


def sample_quant():
    return {
        "annualized_volatility": 28.0, "max_drawdown": -30.0,
        "sharpe_ratio": 1.1, "sortino_ratio": 1.6,
        "hist_var_95_1d": 2.7, "hist_var_99_1d": 4.1,
        "hist_cvar_95_1d": 3.5, "hist_cvar_99_1d": 5.0,
        "param_var_95_10d": 8.0, "cf_mod_var_95_1d": 2.8,
        "beta": 1.18, "alpha": 3.2, "r_squared": 0.6,
        "skewness": -0.1, "kurtosis": 4.0,
    }


def read_sheets(data: bytes) -> dict:
    return pd.read_excel(BytesIO(data), sheet_name=None)


def test_report_for_stock_has_all_sheets():
    data = generate_excel_report(
        "Apple Inc.", "aapl", "Technology", "Consumer Electronics", 200.0, "$",
        valuation={"current_pe": 30.0, "avg_pe": 25.0, "premium_pct": 20.0, "is_loss_making": False},
        fcf={"yield_pct": 3.2},
        div_metrics={"yield_pct": 0.5, "payout_pct": 15.0},
        piotroski_result={"criteria": {"Positive ROA": True, "Cash Quality": False}},
        debt_metrics={"debt_to_equity": 1.2, "interest_coverage": 20.0},
        quant_metrics=sample_quant(), benchmark_name="S&P 500",
        is_financial=False, is_commodity=False,
    )
    sheets = read_sheets(data)
    assert set(sheets) == {"Overview", "Valuation & Debt", "Piotroski Details", "Quantitative Risk"}
    assert sheets["Overview"]["Value"].tolist()[1] == "AAPL"
    assert "S&P 500" in sheets["Quantitative Risk"]["Value"].tolist()


def test_report_for_commodity_has_no_fundamental_sheets():
    data = generate_excel_report(
        "Gold Futures", "GC=F", None, None, 2000.0, "$",
        valuation=None, fcf=None, div_metrics=None, piotroski_result=None, debt_metrics=None,
        quant_metrics=sample_quant(), benchmark_name=None,
        is_financial=False, is_commodity=True,
    )
    assert set(read_sheets(data)) == {"Overview", "Quantitative Risk"}# -*- coding: utf-8 -*-

