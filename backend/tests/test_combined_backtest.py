from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.signal_event import SignalEvent, SignalNotification
from app.services.analysis.combined_backtest import run_combined_backtest
from app.services.market_data.base import NormalizedCandle
from app.api.signals import record_signal


def candles(count=180):
    rows = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        close = 100 + i * 0.12 + (2 if (i // 30) % 2 else 0)
        open_price = close - 0.08
        rows.append(NormalizedCandle(
            symbol="BTCUSDT", timeframe="1h",
            open_time=start + timedelta(hours=i),
            close_time=start + timedelta(hours=i, minutes=59),
            open=open_price, high=close + 0.3, low=open_price - 0.3,
            close=close, volume=100.0, quote_volume=close * 100,
            trades=100, taker_buy_volume=55.0,
        ))
    return rows


def test_combined_backtest_reports_out_of_sample_and_quality_gates():
    result = run_combined_backtest(candles())
    assert result["candles"] == 180
    assert "out_of_sample" in result
    assert set(result["quality_checks"]) == {
        "minimum_oos_trades_met", "positive_oos_expectancy", "oos_drawdown_below_20pct"
    }
    assert result["fee_bps_per_side"] == 10.0
    assert result["slippage_bps_per_side"] == 5.0
    assert result["limitations"]


def test_combined_backtest_validates_history_and_horizon():
    with pytest.raises(ValueError, match="140"):
        run_combined_backtest(candles(100))
    with pytest.raises(ValueError, match="Horizon"):
        run_combined_backtest(candles(), horizon=30)


def test_signal_lifecycle_deduplicates_invalidates_and_notifies():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        record_signal(db, "BTCUSDT", "BUY", ["15m", "1h"], ["bullish"], "2026-11-15T10:00:00+00:00")
        record_signal(db, "BTCUSDT", "BUY", ["15m", "1h"], ["bullish"], "2026-11-15T10:00:00+00:00")
        events = db.scalars(select(SignalEvent)).all()
        notices = db.scalars(select(SignalNotification)).all()
        assert len(events) == 1
        assert len(notices) == 1
        events[0].status = "CLOSED"
        db.commit()
        record_signal(
            db, "BTCUSDT", "BUY", ["15m", "1h"], ["bullish"],
            "2026-11-15T10:00:00+00:00"
        )
        assert len(db.scalars(select(SignalEvent)).all()) == 1
        record_signal(
            db, "BTCUSDT", "SELL", ["15m", "1h"], ["bearish"],
            "2026-11-15T11:00:00+00:00"
        )
        events = db.scalars(select(SignalEvent).order_by(SignalEvent.id)).all()
        assert [event.status for event in events] == ["INVALIDATED", "ACTIVE"]
        assert len(db.scalars(select(SignalNotification)).all()) == 2
        record_signal(db, "BTCUSDT", "NO TRADE", ["15m", "1h"], [], "2026-11-15T12:00:00+00:00")
        assert db.scalar(select(SignalEvent).where(SignalEvent.status == "ACTIVE")) is None
    engine.dispose()
