import json

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



def test_signal_creation_and_result_send_push_without_breaking_persistence(monkeypatch):
    from app.api import signals as signal_api
    from app.api.signals import evaluate_active_signals

    calls = []

    def fake_push(_db, **kwargs):
        calls.append(kwargs)
        return {"sent": 1, "failed": 0, "configured": 1}

    monkeypatch.setattr(signal_api, "send_push_to_registered_devices", fake_push, raising=False)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        plan = {"entry": 100.0, "stop_loss": 98.0, "take_profit": 104.0}
        record_signal(
            db, "PUSHTEST", "BUY", ["4h", "1h", "15m"], ["aligned"],
            "push-signal-1", plan, "push-candle-1",
        )
        assert len(calls) == 1
        assert calls[0]["data"]["type"] == "trade_signal"

        record_signal(
            db, "PUSHTEST", "BUY", ["4h", "1h", "15m"], ["still aligned"],
            "push-signal-2", plan, "push-candle-2",
        )
        assert len(calls) == 1

        evaluate_active_signals(db, "PUSHTEST", 105.0, 99.0, "push-candle-3")
        assert len(calls) == 2
        assert calls[1]["data"]["type"] == "trade_result"
        assert calls[1]["data"]["outcome"] == "TP"
        event = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "PUSHTEST"))
        assert event.status == "CLOSED"
        assert json.loads(event.reasons_json)["outcome"] == "TP"
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_signal_outcome_is_saved_when_push_provider_raises(monkeypatch):
    from app.api import signals as signal_api
    from app.api.signals import evaluate_active_signals

    def failing_push(*_args, **_kwargs):
        raise RuntimeError("simulated FCM outage")

    monkeypatch.setattr(signal_api, "send_push_to_registered_devices", failing_push, raising=False)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        record_signal(
            db, "PUSHFAIL", "SELL", ["4h", "1h", "15m"], ["aligned"],
            "fail-signal-1",
            {"entry": 100.0, "stop_loss": 102.0, "take_profit": 96.0},
            "fail-candle-1",
        )
        evaluate_active_signals(db, "PUSHFAIL", 101.0, 95.0, "fail-candle-2")
        event = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "PUSHFAIL"))
        assert event.status == "CLOSED"
        assert json.loads(event.reasons_json)["outcome"] == "TP"
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()
