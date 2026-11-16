from sqlalchemy import delete, select

from app.api.signals import record_signal
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models.signal_event import SignalEvent, SignalNotification


def test_signal_lifecycle_deduplicates_and_invalidates_cleanly():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()

        record_signal(
            db, "BTCUSDT", "BUY", ["15m", "1h"], ["Bullish alignment"], "candle-1"
        )
        first_events = list(db.scalars(select(SignalEvent)))
        first_notifications = list(db.scalars(select(SignalNotification)))
        assert len(first_events) == 1
        assert first_events[0].status == "ACTIVE"
        assert len(first_notifications) == 1

        # A continuing same-side setup refreshes the active event without alert spam.
        record_signal(
            db, "BTCUSDT", "BUY", ["15m", "1h"], ["Still bullish"], "candle-2"
        )
        assert len(list(db.scalars(select(SignalEvent)))) == 1
        assert len(list(db.scalars(select(SignalNotification)))) == 1

        # An opposite signal invalidates the old setup and creates a fresh alert.
        record_signal(
            db, "BTCUSDT", "SELL", ["15m", "1h"], ["Bearish reversal"], "candle-3"
        )
        events = list(db.scalars(select(SignalEvent).order_by(SignalEvent.id)))
        notifications = list(db.scalars(select(SignalNotification)))
        assert [event.status for event in events] == ["INVALIDATED", "ACTIVE"]
        assert [event.side for event in events] == ["BUY", "SELL"]
        assert len(notifications) == 2

        # NO TRADE invalidates the currently active setup without creating an alert.
        record_signal(
            db, "BTCUSDT", "NO TRADE", ["15m", "1h"], ["Confluence lost"], "candle-4"
        )
        assert all(
            event.status == "INVALIDATED"
            for event in db.scalars(select(SignalEvent))
        )
        assert len(list(db.scalars(select(SignalNotification)))) == 2
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()



def test_signal_outcomes_track_tp_and_exclude_ambiguous_candles():
    from app.api.signals import evaluate_active_signals

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        plan = {"entry": 100.0, "stop_loss": 98.0, "take_profit": 104.0}
        record_signal(
            db, "TPTEST", "BUY", ["4h", "1h", "15m"], ["setup"],
            "signal-tp", plan, "candle-tp-1",
        )
        record_signal(
            db, "AMBTEST", "BUY", ["4h", "1h", "15m"], ["setup"],
            "signal-amb", plan, "candle-amb-1",
        )

        # The signal candle itself must never close its own trade.
        evaluate_active_signals(db, "TPTEST", 105.0, 97.0, "candle-tp-1")
        tp_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "TPTEST"))
        assert tp_row.status == "ACTIVE"

        evaluate_active_signals(db, "TPTEST", 105.0, 99.0, "candle-tp-2")
        tp_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "TPTEST"))
        tp_payload = json.loads(tp_row.reasons_json)
        assert tp_row.status == "CLOSED"
        assert tp_payload["outcome"] == "TP"
        assert tp_payload["realized_r"] == 2.0

        # If TP and SL occur in one OHLC candle, do not guess the order.
        evaluate_active_signals(db, "AMBTEST", 105.0, 97.0, "candle-amb-2")
        amb_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "AMBTEST"))
        amb_payload = json.loads(amb_row.reasons_json)
        assert amb_row.status == "CLOSED"
        assert amb_payload["outcome"] == "AMBIGUOUS"
        assert amb_payload["realized_r"] is None
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()
