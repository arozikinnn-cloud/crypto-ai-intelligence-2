from datetime import datetime, timezone

import pytest

from app.services.market_data.base import MarketDataError
from app.services.market_data.bitget import BitgetUsdtFuturesMarketData


class FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
async def test_bitget_futures_candles_are_normalized_and_sorted(monkeypatch):
    import app.services.market_data.bitget as module

    async def fake_get_json(client, path, params, source_name):
        assert path == "/api/v2/mix/market/candles"
        assert params["productType"] == "USDT-FUTURES"
        return {
            "code": "00000",
            "data": [
                ["1767229200000", "101", "103", "100", "102", "12", "1224"],
                ["1767225600000", "99", "102", "98", "101", "10", "1000"],
            ],
        }

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(module, "get_json_with_retry", fake_get_json)
    candles = await BitgetUsdtFuturesMarketData().fetch_klines("BTCUSDT", "1h", 2)
    assert len(candles) == 2
    assert candles[0].open_time == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert candles[0].close == 101
    assert candles[1].quote_volume == 1224


@pytest.mark.asyncio
async def test_bitget_rejects_bad_interval_before_network(monkeypatch):
    provider = BitgetUsdtFuturesMarketData()
    with pytest.raises(MarketDataError, match="interval"):
        await provider.fetch_klines("BTCUSDT", "2m", 10)


@pytest.mark.asyncio
async def test_bitget_rejects_exchange_error(monkeypatch):
    import app.services.market_data.bitget as module

    async def fake_get_json(client, path, params, source_name):
        return {"code": "40034", "msg": "invalid symbol"}

    monkeypatch.setattr(module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(module, "get_json_with_retry", fake_get_json)
    with pytest.raises(MarketDataError, match="rejected"):
        await BitgetUsdtFuturesMarketData().fetch_klines("BTCUSDT", "1h", 10)
