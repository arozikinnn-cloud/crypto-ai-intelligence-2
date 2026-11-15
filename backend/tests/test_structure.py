from datetime import datetime, timedelta, timezone
import pytest
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.structure import analyze_structure


def candles_from_closes(closes: list[float]) -> list[NormalizedCandle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = []
    for index, close in enumerate(closes):
        result.append(NormalizedCandle(
            symbol="BTCUSDT", timeframe="1h",
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index, minutes=59),
            open=close - 0.2, high=close + 0.5, low=close - 0.5,
            close=close, volume=100.0, quote_volume=close * 100,
            trades=10,
        ))
    return result


def test_structure_requires_minimum_history():
    with pytest.raises(ValueError):
        analyze_structure(candles_from_closes([100.0] * 10))


def test_structure_returns_smc_fields():
    result = analyze_structure(candles_from_closes([100 + (i % 7) for i in range(80)]))
    assert result["trend"] in {"bullish", "bearish", "range_or_unconfirmed"}
    assert result["event"] in {"none", "bullish_bos", "bearish_bos", "bullish_choch", "bearish_choch"}
    assert result["pivot_count"] >= 0
    assert "method_note" in result
