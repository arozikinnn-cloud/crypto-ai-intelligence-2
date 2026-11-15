from datetime import datetime, timedelta, timezone
import pytest
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.order_flow import analyze_order_flow


def build_candles(buy_volume: float) -> list[NormalizedCandle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        NormalizedCandle(
            symbol="BTCUSDT", timeframe="5m",
            open_time=start + timedelta(minutes=5 * index),
            close_time=start + timedelta(minutes=5 * index + 4),
            open=100, high=102, low=99, close=101,
            volume=10, quote_volume=1010, trades=10,
            taker_buy_volume=buy_volume,
        )
        for index in range(5)
    ]


def test_order_flow_detects_buy_pressure():
    result = analyze_order_flow(build_candles(8), lookback=5)
    assert result["bias"] == "BUY_PRESSURE"
    assert result["net_delta"] == 30


def test_order_flow_detects_sell_pressure():
    result = analyze_order_flow(build_candles(2), lookback=5)
    assert result["bias"] == "SELL_PRESSURE"
    assert result["net_delta"] == -30


def test_order_flow_rejects_missing_taker_data():
    candles = build_candles(5)
    candles[0] = NormalizedCandle(
        symbol="BTCUSDT", timeframe="5m",
        open_time=candles[0].open_time, close_time=candles[0].close_time,
        open=100, high=102, low=99, close=101,
        volume=10, quote_volume=1010, trades=10,
    )
    with pytest.raises(ValueError):
        analyze_order_flow(candles, lookback=5)
