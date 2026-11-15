import pytest
from app.services.analysis.intelligence import build_intelligence_decision


def test_intelligence_requires_full_bullish_alignment():
    result = build_intelligence_decision(
        ["BUY", "BUY", "BUY"],
        {"trend": "bullish", "event": "none"},
        {"bias": "BUY_PRESSURE"},
        {"open_interest_change_percent": 1.2, "funding_rate": 0.0001},
    )
    assert result["side"] == "BUY"
    assert result["confluence_score"] == 3
    assert result["max_confluence"] == 3
    assert result["context_notes"]


def test_intelligence_defaults_to_no_trade_when_modules_disagree():
    result = build_intelligence_decision(
        ["BUY", "NO TRADE", "BUY"],
        {"trend": "bullish", "event": "none"},
        {"bias": "BUY_PRESSURE"},
        {"open_interest_change_percent": 1.2, "funding_rate": 0.0001},
    )
    assert result["side"] == "NO TRADE"
    assert result["confluence_score"] < 3


def test_intelligence_supports_bearish_alignment():
    result = build_intelligence_decision(
        ["SELL", "SELL"],
        {"trend": "bearish", "event": "none"},
        {"bias": "SELL_PRESSURE"},
        {"open_interest_change_percent": 0.8, "funding_rate": -0.0001},
    )
    assert result["side"] == "SELL"


def test_derivatives_do_not_create_directional_signal():
    result = build_intelligence_decision(
        ["BUY", "BUY"],
        {"trend": "bullish", "event": "none"},
        {"bias": "BUY_PRESSURE"},
        {"open_interest_change_percent": -1.0, "funding_rate": 0.01},
    )
    assert result["side"] == "BUY"
    assert any("Funding positif" in note for note in result["context_notes"])


def test_unknown_technical_side_is_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        build_intelligence_decision(
            ["LONG"],
            {"trend": "bullish"},
            {"bias": "BUY_PRESSURE"},
            {},
        )
