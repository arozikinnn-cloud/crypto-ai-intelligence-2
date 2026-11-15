from datetime import datetime, timezone
import pytest
from app.services.market_data.base import MarketDataError, NormalizedCandle
from app.services.market_data.quality import validate_candles
from app.services.market_data.binance import BinanceMarketData


def sample_candle(minute: int = 0) -> NormalizedCandle:
    return NormalizedCandle(
        symbol="BTCUSDT", timeframe="1h",
        open_time=datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc),
        close_time=datetime(2026, 1, 1, 0, minute + 1, tzinfo=timezone.utc),
        open=100.0, high=110.0, low=90.0, close=105.0,
        volume=2.0, quote_volume=205.0, trades=10,
    )


def test_quality_accepts_valid_candle_sequence():
    validate_candles([sample_candle(0), sample_candle(2)])


def test_quality_rejects_duplicate_or_unsorted_timestamps():
    with pytest.raises(MarketDataError):
        validate_candles([sample_candle(2), sample_candle(0)])


def test_quality_rejects_inconsistent_ohlc():
    candle = sample_candle()
    invalid = NormalizedCandle(**{**candle.__dict__, "high": 101.0})
    with pytest.raises(MarketDataError):
        validate_candles([invalid])


@pytest.mark.asyncio
async def test_binance_rejects_invalid_symbol_before_network_call():
    provider = BinanceMarketData()
    with pytest.raises(MarketDataError):
        await provider.fetch_klines("BTC/USDT", "1h", 10)
