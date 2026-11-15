from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_returns_running_status():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint():
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_order_flow_endpoint_returns_proxy_metadata(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app.services.market_data.base import NormalizedCandle
    from app.services.market_data.binance import BinanceMarketData

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = [
        NormalizedCandle(
            symbol="BTCUSDT", timeframe="5m",
            open_time=start + timedelta(minutes=5 * index),
            close_time=start + timedelta(minutes=5 * index + 4),
            open=100, high=102, low=99, close=101,
            volume=10, quote_volume=1010, trades=10, taker_buy_volume=8,
        )
        for index in range(3)
    ]

    async def fake_fetch(self, symbol, interval, limit, closed_only=False):
        assert closed_only is True
        return candles

    monkeypatch.setattr(BinanceMarketData, "fetch_klines", fake_fetch)
    response = client.get("/api/v1/analysis/order-flow?lookback=3")
    assert response.status_code == 200
    assert response.json()["bias"] == "BUY_PRESSURE"
    assert "not DOM/footprint" in response.json()["method_note"]


def test_derivatives_endpoint_returns_public_context(monkeypatch):
    from app.services.market_data.binance_futures import BinanceFuturesMarketData

    async def fake_fetch(self, symbol, period):
        return {
            "symbol": symbol,
            "open_interest": 1234.5,
            "open_interest_change_percent": 1.2,
            "open_interest_period": period,
            "funding_rate": 0.0001,
            "funding_time": 1767225600000,
            "interpretation": "OI is not directional by itself.",
        }

    monkeypatch.setattr(
        BinanceFuturesMarketData, "fetch_derivatives_context", fake_fetch
    )
    response = client.get("/api/v1/analysis/derivatives?symbol=BTCUSDT&period=5m")
    assert response.status_code == 200
    assert response.json()["open_interest"] == 1234.5
