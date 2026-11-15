from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.services.analysis.structure import analyze_structure
from app.services.market_data.base import NormalizedCandle


def candles_from_closes(closes: list[float]) -> list[NormalizedCandle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = []
    for index, close in enumerate(closes):
        result.append(
            NormalizedCandle(
                symbol="BTCUSDT",
                timeframe="1h",
                open_time=start + timedelta(hours=index),
                close_time=start + timedelta(hours=index, minutes=59),
                open=close - 0.2,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                volume=100.0,
                quote_volume=close * 100,
                trades=10,
            )
        )
    return result


def test_structure_requires_minimum_history():
    with pytest.raises(ValueError):
        analyze_structure(candles_from_closes([100.0] * 10))


def test_structure_returns_smc_fields():
    closes = [100 + (index % 7) for index in range(80)]
    result = analyze_structure(candles_from_closes(closes))
    assert result["trend"] in {"bullish", "bearish", "range_or_unconfirmed"}
    allowed_events = {
        "none", "bullish_bos", "bearish_bos", "bullish_choch", "bearish_choch"
    }
    assert result["event"] in allowed_events
    assert result["liquidity_sweep"] in {
        "none", "bullish_sweep", "bearish_sweep", "both_sides_swept"
    }
    assert "bullish_order_block" in result
    assert "bearish_order_block" in result
    assert result["pivot_count"] >= 0
    assert "method_note" in result


def test_structure_detects_bearish_liquidity_sweep():
    candles = candles_from_closes([100 + (index % 7) for index in range(80)])
    baseline = analyze_structure(candles)
    swing_high = baseline["last_swing_high"]
    assert swing_high is not None
    close = swing_high - 0.1
    candles[-1] = replace(
        candles[-1],
        open=close + 0.2,
        high=swing_high + 0.5,
        low=close - 0.5,
        close=close,
    )
    result = analyze_structure(candles)
    assert result["liquidity_sweep"] == "bearish_sweep"


def test_structure_finds_order_block_before_bullish_break():
    candles = candles_from_closes([100 + (index % 7) for index in range(80)])
    baseline = analyze_structure(candles)
    swing_high = baseline["last_swing_high"]
    assert swing_high is not None
    close = swing_high + 1.0
    candles[-1] = replace(
        candles[-1],
        open=close - 0.5,
        high=close + 0.5,
        low=close - 1.0,
        close=close,
    )
    result = analyze_structure(candles)
    assert result["event"].startswith("bullish_")
    assert result["bullish_order_block"] is not None
