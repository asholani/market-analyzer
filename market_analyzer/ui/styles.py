"""Dashboard styling: custom CSS injected into the Streamlit page."""

from __future__ import annotations

import streamlit as st

PALETTE = {
    "background": "#0B0F19",
    "surface": "#111827",
    "border": "#1E293B",
    "text": "#E2E8F0",
    "text_strong": "#F8FAFC",
    "text_muted": "#94A3B8",
    "text_faint": "#64748B",
    "accent": "#FF4B4B",
    "positive": "#10B981",
    "negative": "#EF4444",
    "primary": "#2962FF",
}

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Inter:wght@400;500;600;700;800&display=swap');

/* Global canvas */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0B0F19 !important;
    color: #E2E8F0 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}
[data-testid="stHeader"] { background-color: #0B0F19 !important; }
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
    max-width: 1380px !important;
}

/* Structured data cards */
div[data-testid="stMetric"], div[data-testid="stDataFrame"] {
    background: #111827 !important;
    border: 1px solid #1E293B !important;
    border-radius: 6px !important;
    padding: 0.8rem 1rem !important;
}

/* Dense financial metric typography */
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.25rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em !important;
    color: #F8FAFC !important;
}
div[data-testid="stMetricLabel"] {
    font-size: 0.70rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    color: #94A3B8 !important;
    font-weight: 600 !important;
}
div[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}

/* Hairline dividers */
hr {
    margin-top: 1.4rem !important;
    margin-bottom: 1.4rem !important;
    border: none !important;
    height: 1px !important;
    background-color: #1E293B !important;
}

/* Section headers */
h1 {
    font-size: 1.75rem !important;
    font-weight: 800 !important;
    color: #F8FAFC !important;
    letter-spacing: -0.02em !important;
}
h2, h3 {
    font-size: 1.25rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.03em !important;
    color: #F8FAFC !important;
    font-weight: 700 !important;
    margin-top: 0.5rem !important;
    margin-bottom: 1rem !important;
}

/* Timeframe pills */
div[data-testid="stPills"] button {
    background-color: #111827 !important;
    color: #94A3B8 !important;
    border: 1px solid #1E293B !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.72rem !important;
    padding: 0.2rem 0.6rem !important;
    border-radius: 4px !important;
}
div[data-testid="stPills"] button[aria-checked="true"] {
    color: #F8FAFC !important;
    border-color: #334155 !important;
    font-weight: 600 !important;
}

/* Tabs (red accent) */
button[data-baseweb="tab"] {
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    color: #64748B !important;
    padding-top: 0.6rem !important;
    padding-bottom: 0.6rem !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #FF4B4B !important;
    border-bottom-color: #FF4B4B !important;
}
div[data-baseweb="tab-highlight"] { background-color: #FF4B4B !important; }

/* Checkbox */
div[data-testid="stCheckbox"] label span:first-child { border-color: #334155 !important; }

/* Expanders */
div[data-testid="stExpander"] {
    background: #111827 !important;
    border: 1px solid #1E293B !important;
    border-radius: 6px !important;
}

/* Search input box */
div[data-baseweb="select"] {
    background-color: #111827 !important;
    border-radius: 6px !important;
}
</style>
"""


def apply_theme() -> None:
    """Inject the dashboard CSS. Call once, right after st.set_page_config()."""
    st.markdown(THEME_CSS, unsafe_allow_html=True)

