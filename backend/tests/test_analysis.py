from datetime import datetime, timedelta, timezone
import pytest
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.indicators import calculate_indicators, validate_analysis_input
from app.services.analysis.engine import analyze_market


def make_candles(direction: float = 1.0, count: int = 100) -> list[NormalizedCandle]:
    candles = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    for index in range(count):
        previous = price
        price += direction * 0.3
        candles.append(
            NormalizedCandle(
                symbol="BTCUSDT",
                timeframe="1h",
                open_time=start + timedelta(hours=index),
                close_time=start + timedelta(hours=index, minutes=59),
                open=previous,
                high=max(previous, price) + 0.2,
                low=min(previous, price) - 0.2,
                close=price,
                volume=100.0 + index,
                quote_volume=(100.0 + index) * price,
                trades=100,
            )
        )
    return candles


def test_indicators_return_expected_fields():
    result = calculate_indicators(make_candles())
    assert result["ema20"] is not None
    assert result["ema50"] is not None
    assert result["rsi14"] == 100.0
    assert result["atr14"] is not None
    assert result["market_structure"] in {
        "higher_high_higher_low", "lower_high_lower_low", "mixed_or_range"
    }


def test_analysis_rejects_insufficient_history():
    with pytest.raises(ValueError):
        validate_analysis_input(make_candles(count=30))


def test_analysis_returns_explainable_output():
    result = analyze_market(make_candles())
    assert result["side"] in {"BUY", "SELL", "NO TRADE"}
    assert result["max_confluence"] == 4
    if result["side"] != "NO TRADE":
        assert result["risk_reward"] == 1.5
    assert result["reasons"]
    assert result["score_note"].startswith("Skor konfluensi")
