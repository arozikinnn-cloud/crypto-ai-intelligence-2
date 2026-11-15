import pytest

from app.services.market_data.binance_aggtrades import BinanceAggTradesMarketData
from app.services.market_data.base import MarketDataError


@pytest.mark.asyncio
async def test_aggtrades_maps_buyer_maker_to_aggressor_side(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"a": 1, "T": 1000, "q": "2.0", "m": False},
                {"a": 2, "T": 2000, "q": "1.0", "m": True},
                {"a": 3, "T": 3000, "q": "1.0", "m": False},
            ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(
        "app.services.market_data.binance_aggtrades.httpx.AsyncClient", FakeClient
    )
    result = await BinanceAggTradesMarketData().fetch_order_flow("BTCUSDT", 10)

    assert result["buy_aggressor_volume"] == 3.0
    assert result["sell_aggressor_volume"] == 1.0
    assert result["net_delta"] == 2.0
    assert result["bias"] == "BUY_PRESSURE"
    assert result["trade_count"] == 3


@pytest.mark.asyncio
async def test_aggtrades_rejects_invalid_symbol_without_network():
    with pytest.raises(MarketDataError, match="Invalid trading symbol"):
        await BinanceAggTradesMarketData().fetch_order_flow("BTC/USDT", 100)
