from datetime import datetime, timedelta, timezone
import pytest
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.order_flow import analyze_order_flow


def build_candles(buy_volume: float | None, count: int = 5) -> list[NormalizedCandle]:
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
        for index in range(count)
    ]


def test_order_flow_detects_buy_pressure_and_window_delta():
    result = analyze_order_flow(build_candles(8), lookback=5)
    assert result["bias"] == "BUY_PRESSURE"
    assert result["net_delta"] == 30
    assert result["cumulative_delta"] == 30
    assert result["buy_volume"] == 40
    assert result["sell_volume"] == 10


def test_order_flow_detects_sell_pressure():
    result = analyze_order_flow(build_candles(2), lookback=5)
    assert result["bias"] == "SELL_PRESSURE"
    assert result["net_delta"] == -30


def test_order_flow_requires_full_lookback():
    with pytest.raises(ValueError, match="At least 5"):
        analyze_order_flow(build_candles(5, count=4), lookback=5)


def test_order_flow_rejects_missing_taker_data():
    with pytest.raises(ValueError, match="unavailable"):
        analyze_order_flow(build_candles(None), lookback=5)


def test_order_flow_rejects_inconsistent_symbol():
    candles = build_candles(5)
    candles[-1] = NormalizedCandle(**{**candles[-1].__dict__, "symbol": "ETHUSDT"})
    with pytest.raises(ValueError, match="consistent"):
        analyze_order_flow(candles, lookback=5)


def test_order_flow_rejects_non_finite_data():
    candles = build_candles(5)
    candles[-1] = NormalizedCandle(**{
        **candles[-1].__dict__, "taker_buy_volume": float("nan")
    })
    with pytest.raises(ValueError, match="non-finite"):
        analyze_order_flow(candles, lookback=5)
