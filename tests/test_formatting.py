import numpy as np
import pandas as pd

from market_analyzer.utils.formatting import (
    format_financial_value,
    get_currency_symbol,
    safe_get_metric,
    safe_str,
)


def test_format_financial_value_scales():
    assert format_financial_value(1_500_000_000, "$") == "$1.50B"
    assert format_financial_value(2_500_000, "€") == "€2.5M"
    assert format_financial_value(-1_500_000_000, "$") == "-$1.50B"
    assert format_financial_value(500, "$") == "$500"


def test_format_financial_value_missing():
    assert format_financial_value(None) == "N/A"
    assert format_financial_value(np.nan) == "N/A"


def test_safe_str():
    assert safe_str(None) == "N/A"
    assert safe_str(float("nan")) == "N/A"
    assert safe_str("Apple") == "Apple"


def test_currency_symbol():
    assert get_currency_symbol("eur") == "€"
    assert get_currency_symbol("XYZ") == "XYZ"
    assert get_currency_symbol(None) == "$"


def test_safe_get_metric_tries_fallback_labels():
    df = pd.DataFrame({"2023": [100.0, np.nan]}, index=["Operating Revenue", "Total Revenue"])
    assert safe_get_metric(df, ["Total Revenue", "Operating Revenue"], "2023") == 100.0
    assert safe_get_metric(df, ["Unknown"], "2023") is None
    assert safe_get_metric(None, ["Total Revenue"], "2023") is None