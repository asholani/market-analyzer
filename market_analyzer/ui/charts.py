"""Altair chart builders. Each function takes data and returns a chart (no Streamlit calls)."""

from __future__ import annotations

import altair as alt
import pandas as pd

from market_analyzer.ui.styles import PALETTE

CHART_HEIGHT = 320


def _axis(**kwargs) -> alt.Axis:
    """Shared axis style: muted labels, hairline grid."""
    base = dict(
        labelColor=PALETTE["text_muted"],
        titleColor=PALETTE["text_muted"],
        gridColor=PALETTE["border"],
        domainColor=PALETTE["border"],
    )
    base.update(kwargs)
    return alt.Axis(**base)


def _finalize(chart, height: int):
    """Apply the dark background and remove the frame."""
    return chart.properties(height=height, background=PALETTE["background"]).configure_view(strokeWidth=0)


def _padded_domain(series: pd.Series, margin: float = 0.02) -> list[float]:
    """Y-axis domain slightly wider than the data, so the line does not touch the edges."""
    return [float(series.min()) * (1 - margin), float(series.max()) * (1 + margin)]


def _date_column(df: pd.DataFrame) -> str:
    """Name of the datetime column after reset_index()."""
    for name in ("Datetime", "Date"):
        if name in df.columns:
            return name
    return df.columns[0]


def price_chart(
    history: pd.DataFrame,
    ticker: str,
    currency_sym: str,
    bench_history: pd.DataFrame | None = None,
    bench_name: str | None = None,
):
    """Price line, with an optional benchmark on an independent right-hand axis."""
    data = history.reset_index()
    date_col = _date_column(data)

    asset_line = (
        alt.Chart(data)
        .mark_line(color=PALETTE["primary"], strokeWidth=2)
        .encode(
            x=alt.X(f"{date_col}:T", title=None, axis=_axis()),
            y=alt.Y(
                "Close:Q",
                title=f"{ticker.upper()} ({currency_sym})",
                scale=alt.Scale(domain=_padded_domain(data["Close"].dropna()), zero=False),
                axis=_axis(),
            ),
            tooltip=[
                alt.Tooltip(f"{date_col}:T", title="Time"),
                alt.Tooltip("Close:Q", title=f"{ticker.upper()} ({currency_sym})", format=".2f"),
            ],
        )
    )

    if bench_history is None or bench_history.empty or "Close" not in bench_history:
        return _finalize(asset_line, CHART_HEIGHT).interactive()

    b_data = bench_history.reset_index()
    b_date_col = _date_column(b_data)
    bench_line = (
        alt.Chart(b_data)
        .mark_line(color=PALETTE["text_muted"], strokeWidth=1.5, strokeDash=[4, 3])
        .encode(
            x=alt.X(f"{b_date_col}:T"),
            y=alt.Y(
                "Close:Q",
                title=f"{bench_name} (pts)",
                scale=alt.Scale(domain=_padded_domain(b_data["Close"].dropna()), zero=False),
                axis=_axis(orient="right", grid=False),
            ),
            tooltip=[
                alt.Tooltip(f"{b_date_col}:T", title="Time"),
                alt.Tooltip("Close:Q", title=str(bench_name), format=",.2f"),
            ],
        )
    )
    return _finalize(
        alt.layer(asset_line, bench_line).resolve_scale(y="independent"), CHART_HEIGHT
    ).interactive()


def revenue_net_income_chart(revenue: float, net_income: float, currency_sym: str):
    """Two bars: revenue and net income for one fiscal year."""
    df = pd.DataFrame({"Metric": ["Revenue", "Net Income"], "Amount": [revenue, net_income]})
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=160)
        .encode(
            x=alt.X(
                "Metric:N",
                sort=["Revenue", "Net Income"],
                scale=alt.Scale(paddingInner=0.45, paddingOuter=0.35),
                title=None,
                axis=_axis(labelColor=PALETTE["text"], labelFontSize=13, labelFontWeight="bold", labelAngle=0),
            ),
            y=alt.Y("Amount:Q", title=f"Amount ({currency_sym})", axis=_axis()),
            color=alt.Color(
                "Metric:N",
                scale=alt.Scale(
                    domain=["Revenue", "Net Income"],
                    range=[PALETTE["primary"], PALETTE["positive"]],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Metric:N", title="Item"),
                alt.Tooltip("Amount:Q", title=f"Amount ({currency_sym})", format=",.0f"),
            ],
        )
    )
    return _finalize(chart, 300)


def analyst_chart(distribution: dict[str, float]):
    """Buy / Hold / Sell share bars. `distribution` maps label -> percentage."""
    df = pd.DataFrame({
        "Recommendation": list(distribution.keys()),
        "Share (%)": [round(v, 1) for v in distribution.values()],
    })
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=48)
        .encode(
            x=alt.X(
                "Recommendation:N",
                sort=["Buy", "Hold", "Sell"],
                title=None,
                axis=_axis(labelColor=PALETTE["text"], labelFontSize=12, labelFontWeight="bold", labelAngle=0),
            ),
            y=alt.Y("Share (%):Q", title="Share (%)", axis=_axis()),
            color=alt.Color(
                "Recommendation:N",
                scale=alt.Scale(
                    domain=["Buy", "Hold", "Sell"],
                    range=[PALETTE["positive"], "#7DD3FC", PALETTE["negative"]],
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("Recommendation:N", title="Recommendation"),
                alt.Tooltip("Share (%):Q", title="Share (%)", format=".1f"),
            ],
        )
    )
    return _finalize(chart, 220)


def return_distribution_chart(returns_pct: pd.Series, var_95: float, cvar_95: float):
    """Histogram of daily returns (%), with vertical lines at the 95% VaR and CVaR.

    `var_95` and `cvar_95` are the (negative) return thresholds, e.g. -2.7.
    """
    hist_df = pd.DataFrame({"Return": returns_pct})
    amber = "#F59E0B"

    hist = (
        alt.Chart(hist_df)
        .mark_bar(color=PALETTE["border"], stroke=PALETTE["primary"], strokeWidth=0.8, opacity=0.7)
        .encode(
            x=alt.X("Return:Q", bin=alt.Bin(maxbins=50), title="Daily Return (%)", axis=_axis()),
            y=alt.Y("count()", title="Frequency", axis=_axis()),
            tooltip=[alt.Tooltip("count()", title="Occurrences")],
        )
    )

    rules_df = pd.DataFrame([
        {"Threshold": var_95, "Color": amber},
        {"Threshold": cvar_95, "Color": PALETTE["negative"]},
    ])
    rules = (
        alt.Chart(rules_df)
        .mark_rule(strokeDash=[4, 4], strokeWidth=2)
        .encode(x="Threshold:Q", color=alt.Color("Color:N", scale=None))
    )

    def label(value: float, text: str, color: str, dy: int):
        return (
            alt.Chart(pd.DataFrame([{"Threshold": value, "Label": f"{text} ({value:.2f}%)"}]))
            .mark_text(
                align="right", baseline="top", dx=-6, dy=dy,
                fontSize=11, fontWeight="bold", font="JetBrains Mono", color=color,
            )
            .encode(x="Threshold:Q", text="Label:N")
        )

    layered = hist + rules + label(var_95, "VaR 95%", amber, 6) + label(cvar_95, "CVaR 95%", PALETTE["negative"], 24)
    return _finalize(layered, 260)

