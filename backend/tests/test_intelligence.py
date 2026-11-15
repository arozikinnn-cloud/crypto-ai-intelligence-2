from app.services.analysis.intelligence import build_intelligence_decision


def test_intelligence_requires_full_bullish_alignment():
    result = build_intelligence_decision(
        ["BUY", "BUY", "BUY"],
        {"trend": "bullish", "event": "none"},
        {"bias": "BUY_PRESSURE"},
        {"open_interest_change_percent": 1.2, "funding_rate": 0.0001},
    )
    assert result["side"] == "BUY"
    assert result["confluence_score"] == 5


def test_intelligence_defaults_to_no_trade_when_modules_disagree():
    result = build_intelligence_decision(
        ["BUY", "NO TRADE", "BUY"],
        {"trend": "bullish", "event": "none"},
        {"bias": "BUY_PRESSURE"},
        {"open_interest_change_percent": 1.2, "funding_rate": 0.0001},
    )
    assert result["side"] == "NO TRADE"
    assert result["confluence_score"] < 5


def test_intelligence_supports_bearish_alignment():
    result = build_intelligence_decision(
        ["SELL", "SELL"],
        {"trend": "bearish", "event": "none"},
        {"bias": "SELL_PRESSURE"},
        {"open_interest_change_percent": 0.8, "funding_rate": -0.0001},
    )
    assert result["side"] == "SELL"
