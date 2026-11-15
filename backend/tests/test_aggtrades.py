import pytest

from app.services.market_data.binance_aggtrades import BinanceAggTradesMarketData
from app.services.market_data.base import MarketDataError


@pytest.mark.asyncio
async def test_aggtrades_maps_buyer_maker_and_builds_cvd_buckets(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"a": 1, "T": 60_001, "q": "2.0", "m": False},
                {"a": 2, "T": 60_500, "q": "1.0", "m": True},
                {"a": 3, "T": 120_001, "q": "1.0", "m": False},
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
    assert result["cvd_scope"] == "returned_batch_only"
    assert [point["delta"] for point in result["cvd_points"]] == [1.0, 1.0]
    assert [point["cumulative_delta"] for point in result["cvd_points"]] == [1.0, 2.0]
    assert result["cumulative_delta"] == 2.0


@pytest.mark.asyncio
async def test_aggtrades_rejects_invalid_symbol_without_network():
    with pytest.raises(MarketDataError, match="Invalid trading symbol"):
        await BinanceAggTradesMarketData().fetch_order_flow("BTC/USDT", 100)


@pytest.mark.asyncio
async def test_aggtrades_rejects_non_positive_quantity(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"a": 1, "T": 1000, "q": "0", "m": False}]

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
    with pytest.raises(MarketDataError, match="malformed aggregated-trades"):
        await BinanceAggTradesMarketData().fetch_order_flow("BTCUSDT", 10)
