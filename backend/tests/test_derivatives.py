import pytest
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance_futures import BinanceFuturesMarketData


@pytest.mark.asyncio
async def test_derivatives_rejects_invalid_symbol_without_network():
    provider = BinanceFuturesMarketData()
    with pytest.raises(MarketDataError, match="Invalid trading symbol"):
        await provider.fetch_derivatives_context("BTC/USDT")


@pytest.mark.asyncio
async def test_derivatives_rejects_unsupported_period_without_network():
    provider = BinanceFuturesMarketData()
    with pytest.raises(MarketDataError, match="Unsupported"):
        await provider.fetch_derivatives_context("BTCUSDT", "2m")
