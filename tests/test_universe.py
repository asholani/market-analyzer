from market_analyzer.data.universe import clean_ticker


def test_clean_ticker_us_class_shares():
    assert clean_ticker("BRK.B") == "BRK-B"


def test_clean_ticker_adds_exchange_suffix():
    assert clean_ticker("AIR", ".PA") == "AIR.PA"
    assert clean_ticker("SAP", ".DE") == "SAP.DE"


def test_clean_ticker_does_not_duplicate_suffix():
    assert clean_ticker("AIR.PA", ".PA") == "AIR.PA"


def test_clean_ticker_strips_wikipedia_footnotes():
    assert clean_ticker("MSFT[1]") == "MSFT"# -*- coding: utf-8 -*-

