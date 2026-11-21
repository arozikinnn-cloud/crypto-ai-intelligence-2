from types import SimpleNamespace

from worker import (configured_collectors, monitor_active_signals_once, validate_worker_database)
from app.services.market_data.cvd_collector import stream_binance_aggtrades
from app.services.market_data.liquidation_collector import stream_binance_liquidations


def test_configured_collectors_builds_enabled_symbol_streams():
    settings = SimpleNamespace(
        cvd_collector_enabled=True,
        cvd_collector_symbol_list=["BTCUSDT", "ETHUSDT"],
        cvd_collector_flush_interval_seconds=2.0,
        liquidation_collector_enabled=True,
        liquidation_collector_symbol_list=["BTCUSDT"],
        liquidation_collector_flush_interval_seconds=3.0,
    )

    jobs = configured_collectors(settings)

    assert [(name, symbol) for name, _, symbol, _ in jobs] == [
        ("cvd-BTCUSDT", "BTCUSDT"),
        ("cvd-ETHUSDT", "ETHUSDT"),
        ("liquidations-BTCUSDT", "BTCUSDT"),
    ]
    assert jobs[0][1] is stream_binance_aggtrades
    assert jobs[0][3] == 2.0
    assert jobs[2][1] is stream_binance_liquidations
    assert jobs[2][3] == 3.0


def test_configured_collectors_respects_disabled_flags():
    settings = SimpleNamespace(
        cvd_collector_enabled=False,
        cvd_collector_symbol_list=["BTCUSDT"],
        cvd_collector_flush_interval_seconds=2.0,
        liquidation_collector_enabled=False,
        liquidation_collector_symbol_list=["BTCUSDT"],
        liquidation_collector_flush_interval_seconds=2.0,
    )

    assert configured_collectors(settings) == []



def test_production_worker_rejects_sqlite_database():
    settings = SimpleNamespace(app_env="production", database_url="sqlite:///./local.db")

    try:
        validate_worker_database(settings)
    except RuntimeError as exc:
        assert "durable PostgreSQL DATABASE_URL" in str(exc)
    else:
        raise AssertionError("Production worker must reject isolated SQLite.")


def test_development_worker_allows_local_sqlite_database():
    settings = SimpleNamespace(app_env="development", database_url="sqlite:///./local.db")
    validate_worker_database(settings)



def test_worker_signal_monitor_evaluates_active_signal_from_closed_one_minute_candle():
    import asyncio
    import json
    from datetime import datetime, timezone

    from sqlalchemy import delete, select

    from app.api.signals import record_signal
    from app.database.base import Base
    from app.database.session import SessionLocal, engine
    from app.models.signal_event import SignalEvent, SignalNotification

    class FakeMarket:
        async def fetch_klines(self, symbol, interval, limit, closed_only):
            assert symbol == "MONITORTEST"
            assert interval == "1m"
            assert closed_only is True
            return [SimpleNamespace(
                high=104.0,
                low=99.0,
                close_time=datetime(2026, 11, 17, 10, 16, tzinfo=timezone.utc),
            )]

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        record_signal(
            db, "MONITORTEST", "BUY", ["15m", "30m"], ["setup"],
            "monitor-signal",
            {"entry": 100, "stop_loss": 98, "take_profit": 103},
            "older-signal-candle",
        )
    finally:
        db.close()

    evaluated = asyncio.run(monitor_active_signals_once(FakeMarket(), SessionLocal))
    assert evaluated == 1
    db = SessionLocal()
    try:
        event = db.scalar(select(SignalEvent).where(
            SignalEvent.symbol == "MONITORTEST"
        ))
        assert event.status == "CLOSED"
        assert json.loads(event.reasons_json)["outcome"] == "TP"
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_worker_uses_bitget_for_v8_signal_outcomes(monkeypatch):
    import asyncio
    import json
    from datetime import datetime, timezone

    from sqlalchemy import delete, select

    import worker
    from app.api.signals import record_signal
    from app.database.base import Base
    from app.database.session import SessionLocal, engine
    from app.models.signal_event import SignalEvent, SignalNotification

    class FakeBitget:
        async def fetch_klines(self, symbol, interval, limit, closed_only):
            assert symbol == "V8MONITOR"
            assert interval == "1m"
            assert closed_only is True
            return [SimpleNamespace(
                high=104.0,
                low=99.0,
                close_time=datetime(2026, 11, 18, 10, 16, tzinfo=timezone.utc),
            )]

    monkeypatch.setattr(worker, "BitgetUsdtFuturesMarketData", FakeBitget)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        record_signal(
            db,
            "V8MONITOR",
            "BUY",
            ["1h", "30m", "15m", "5m"],
            ["TradingAgents + Bitget aligned."],
            "v8-monitor-signal",
            {"entry": 100, "stop_loss": 98, "take_profit": 103, "risk_reward": 1.5},
            signal_candle_timestamp="older-v8-candle",
            strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
        )
    finally:
        db.close()

    evaluated = asyncio.run(worker.monitor_active_signals_once())
    assert evaluated == 1
    db = SessionLocal()
    try:
        event = db.scalar(select(SignalEvent).where(
            SignalEvent.symbol == "V8MONITOR"
        ))
        stored = json.loads(event.reasons_json)
        assert event.status == "CLOSED"
        assert stored["outcome"] == "WIN"
        assert stored["realized_r"] == 0.34925
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()
