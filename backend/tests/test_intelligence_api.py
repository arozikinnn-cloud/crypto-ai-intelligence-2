from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.market_data.base import NormalizedCandle
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.binance_futures import BinanceFuturesMarketData

client = TestClient(app)


def build_candles(interval: str, count: int = 80) -> list[NormalizedCandle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    price = 100.0
    for index in range(count):
        previous = price
        price += 0.2
        candles.append(
            NormalizedCandle(
                symbol="BTCUSDT",
                timeframe=interval,
                open_time=start + timedelta(minutes=index),
                close_time=start + timedelta(minutes=index + 1),
                open=previous,
                high=price + 0.3,
                low=previous - 0.3,
                close=price,
                volume=10.0,
                quote_volume=price * 10,
                trades=20,
                taker_buy_volume=8.0,
            )
        )
    return candles


def test_combined_intelligence_endpoint_returns_all_module_context(monkeypatch):
    async def fake_klines(self, symbol, interval, limit, closed_only=False):
        assert closed_only is True
        return build_candles(interval, min(limit, 80))

    async def fake_derivatives(self, symbol, period):
        return {
            "symbol": symbol,
            "source_market": "binance_usdm_futures",\n            "open_interest_unit": "contracts",\n            "open_interest": 1000.0,
            "open_interest_change_percent": 1.0,
            "open_interest_period": period,
            "funding_rate": 0.0001,
            "funding_time": 1767225600000,
            "interpretation": "Test context.",
        }

    monkeypatch.setattr(BinanceMarketData, "fetch_klines", fake_klines)
    monkeypatch.setattr(
        BinanceFuturesMarketData, "fetch_derivatives_context", fake_derivatives
    )

    response = client.get("/api/v1/analysis/intelligence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTCUSDT"
    assert payload["side"] in {"BUY", "SELL", "NO TRADE"}
    assert len(payload["timeframe_analyses"]) == 3
    assert payload["order_flow"]["bias"] == "BUY_PRESSURE"
    assert payload["derivatives"]["open_interest"] == 1000.0
    assert payload["max_confluence"] == 3
