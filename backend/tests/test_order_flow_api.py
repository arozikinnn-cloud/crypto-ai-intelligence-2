from datetime import datetime, timedelta, timezone

import pytest

from app.api.order_flow import order_flow_analysis
from app.services.market_data.base import NormalizedCandle
from app.services.market_data.binance import BinanceMarketData


@pytest.mark.asyncio
async def test_order_flow_fetches_extra_row_before_closed_candle_filter(monkeypatch):
    requested = {}

    async def fake_fetch(self, symbol, interval, limit, closed_only):
        requested["limit"] = limit
        requested["closed_only"] = closed_only
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return [
            NormalizedCandle(
                symbol="BTCUSDT",
                timeframe="5m",
                open_time=start + timedelta(minutes=5 * index),
                close_time=start + timedelta(minutes=5 * index + 4),
                open=100,
                high=102,
                low=99,
                close=101,
                volume=10,
                quote_volume=1010,
                trades=10,
                taker_buy_volume=8,
            )
            for index in range(limit - 1)
        ]

    monkeypatch.setattr(BinanceMarketData, "fetch_klines", fake_fetch)
    result = await order_flow_analysis(symbol="BTCUSDT", interval="5m", lookback=20)

    assert requested == {"limit": 21, "closed_only": True}
    assert result.lookback == 20
    assert result.bias == "BUY_PRESSURE"
