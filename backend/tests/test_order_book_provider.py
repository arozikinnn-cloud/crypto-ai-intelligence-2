import pytest

from app.services.market_data.base import MarketDataError
from app.services.market_data.binance_order_book import BinanceOrderBookMarketData


@pytest.mark.asyncio
async def test_order_book_provider_validates_inputs_before_network():
    provider = BinanceOrderBookMarketData()
    with pytest.raises(MarketDataError, match="Invalid trading symbol"):
        await provider.fetch_order_book("BTC/USDT")
    with pytest.raises(MarketDataError, match="depth limit"):
        await provider.fetch_order_book("BTCUSDT", 17)
