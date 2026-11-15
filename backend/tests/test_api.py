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
    assert "bukan DOM/footprint" in response.json()["method_note"]


def test_derivatives_endpoint_returns_public_context(monkeypatch):
    from app.services.market_data.binance_futures import BinanceFuturesMarketData

    async def fake_fetch(self, symbol, period):
        return {
            "symbol": symbol,
            "source_market": "binance_usdm_futures",
            "open_interest_unit": "contracts",
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


def test_combined_intelligence_endpoint_serializes_all_modules(monkeypatch):
    from datetime import datetime, timezone
    from app.api import analysis_intelligence as api
    from app.services.market_data.binance import BinanceMarketData
    from app.services.market_data.binance_futures import BinanceFuturesMarketData
    from app.services.market_data.binance_aggtrades import BinanceAggTradesMarketData

    async def fake_klines(self, symbol, interval, limit, closed_only=False):
        assert closed_only is True
        return [interval]

    async def fake_derivatives(self, symbol, period):
        return {
            "symbol": symbol,
            "source_market": "binance_usdm_futures",
            "open_interest_unit": "contracts",
            "open_interest": 100.0,
            "open_interest_change_percent": 1.0,
            "open_interest_period": period,
            "funding_rate": 0.0001,
            "funding_time": 1767225600000,
            "interpretation": "Context only.",
        }

    async def fake_aggtrades(self, symbol, limit):
        return {
            "symbol": symbol,
            "source_market": "binance_spot_aggtrades",
            "trade_count": 10,
            "buy_aggressor_volume": 5.0,
            "sell_aggressor_volume": 4.0,
            "net_delta": 1.0,
            "delta_percent": 11.11,
            "cumulative_delta": 1.0,
            "cvd_bucket_interval": "1m",
            "cvd_scope": "returned_batch_only",
            "cvd_points": [],
            "bias": "BUY_PRESSURE",
            "first_trade_time": 1767225600000,
            "last_trade_time": 1767225660000,
            "method_note": "Test aggTrades data.",
        }

    now = datetime.now(timezone.utc)

    def fake_technical(items):
        return {
            "symbol": "BTCUSDT",
            "timeframe": items[0],
            "timestamp": now,
            "side": "NO TRADE",
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "risk_reward": None,
            "confluence_score": 2,
            "max_confluence": 4,
            "score_note": "Heuristic only.",
            "indicators": {
                "market_structure": "mixed_or_range",
                "last_price": 100.0,
                "ema20": 99.0,
                "ema50": 98.0,
                "rsi14": 55.0,
                "macd": 1.0,
                "macd_signal": 0.5,
                "atr14": 2.0,
                "volume_ratio": 1.1,
                "support_20": 90.0,
                "resistance_20": 110.0,
            },
            "reasons": ["No full alignment."],
            "candle_count": 60,
        }

    def fake_structure(_candles):
        return {
            "trend": "range_or_unconfirmed",
            "event": "none",
            "liquidity_sweep": "none",
            "last_swing_high": 110.0,
            "last_swing_low": 90.0,
            "bullish_fvg": None,
            "bearish_fvg": None,
            "bullish_order_block": None,
            "bearish_order_block": None,
            "pivot_count": 4,
            "method_note": "Test structure.",
        }

    def fake_flow(candles, lookback):
        return {
            "symbol": "BTCUSDT",
            "timeframe": "5m",
            "source_market": "binance_spot_klines",
            "lookback": lookback,
            "buy_volume": 50.0,
            "sell_volume": 50.0,
            "net_delta": 0.0,
            "delta_percent": 0.0,
            "cumulative_delta": 0.0,
            "bias": "BALANCED",
            "method_note": "Test proxy.",
        }

    def fake_decision(*_args):
        return {
            "side": "NO TRADE",
            "confluence_score": 0,
            "max_confluence": 3,
            "score_note": "Three checks only.",
            "reasons": ["Test no trade."],
            "context_notes": ["OI/funding context only."],
            "checks": {"technical_bullish_alignment": False},
        }

    monkeypatch.setattr(BinanceMarketData, "fetch_klines", fake_klines)
    monkeypatch.setattr(
        BinanceFuturesMarketData, "fetch_derivatives_context", fake_derivatives
    )
    monkeypatch.setattr(
        BinanceAggTradesMarketData, "fetch_order_flow", fake_aggtrades
    )
    monkeypatch.setattr(api, "analyze_market", fake_technical)
    monkeypatch.setattr(api, "analyze_structure", fake_structure)
    monkeypatch.setattr(api, "analyze_order_flow", fake_flow)
    monkeypatch.setattr(api, "build_intelligence_decision", fake_decision)

    response = client.get("/api/v1/analysis/intelligence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["side"] == "NO TRADE"
    assert payload["order_flow"]["source_market"] == "binance_spot_klines"
    assert payload["derivatives"]["source_market"] == "binance_usdm_futures"
    assert payload["aggtrades_order_flow"]["bias"] == "BUY_PRESSURE"
