from app.services.analysis.market_context import (
    summarize_cvd_history,
    summarize_liquidations,
)


def test_cvd_history_summary_computes_pressure_from_observed_buckets():
    result = summarize_cvd_history({
        "points": [
            {"buy_volume": 12.0, "sell_volume": 4.0},
            {"buy_volume": 8.0, "sell_volume": 4.0},
        ]
    })
    assert result["available"] is True
    assert result["bias"] == "BUY_PRESSURE"
    assert result["bucket_count"] == 2
    assert result["net_delta"] == 12.0


def test_empty_cvd_history_is_unavailable_not_neutral():
    result = summarize_cvd_history({"points": []})
    assert result["available"] is False
    assert result["bias"] == "UNAVAILABLE"


def test_liquidation_summary_keeps_long_and_short_separate():
    result = summarize_liquidations({
        "event_count": 2,
        "points": [
            {"side": "BUY", "total_notional": 1000.0},
            {"side": "SELL", "total_notional": 250.0},
        ],
    })
    assert result["short_liquidation_notional"] == 1000.0
    assert result["long_liquidation_notional"] == 250.0
