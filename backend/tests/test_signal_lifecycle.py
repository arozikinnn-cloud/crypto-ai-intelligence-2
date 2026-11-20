import json

from sqlalchemy import delete, select

from app.api.signals import record_signal
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models.signal_event import SignalEvent, SignalNotification


def test_only_one_active_signal_per_symbol_until_tp_or_sl():
    from app.api.signals import evaluate_active_signals

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()

        plan = {"entry": 100.0, "stop_loss": 98.0, "take_profit": 103.0}
        record_signal(
            db, "BTCUSDT", "BUY", ["15m", "30m"], ["Bullish alignment"],
            "candle-1", plan, "signal-candle-1",
        )
        first = list(db.scalars(select(SignalEvent)))
        assert len(first) == 1
        assert first[0].status == "ACTIVE"
        assert len(list(db.scalars(select(SignalNotification)))) == 1

        # Same-side repeats and opposite-side signals are both blocked,
        # including requests made with a different timeframe set.
        record_signal(
            db, "BTCUSDT", "BUY", ["15m", "30m"], ["Still bullish"],
            "candle-2", plan, "signal-candle-2",
        )
        record_signal(
            db, "BTCUSDT", "SELL", ["15m", "30m"], ["Bearish reversal"],
            "candle-3", plan, "signal-candle-3",
        )
        record_signal(
            db, "BTCUSDT", "SELL", ["5m", "15m"], ["Different timeframe"],
            "candle-4", plan, "signal-candle-4",
        )
        events = list(db.scalars(select(SignalEvent).order_by(SignalEvent.id)))
        assert len(events) == 1
        assert events[0].side == "BUY"
        assert events[0].status == "ACTIVE"
        assert len(list(db.scalars(select(SignalNotification)))) == 1

        # A different symbol can still receive its own signal.
        record_signal(
            db, "ETHUSDT", "SELL", ["15m", "30m"], ["Independent symbol"],
            "eth-candle-1",
            {"entry": 100.0, "stop_loss": 102.0, "take_profit": 97.0},
            "eth-signal-candle-1",
        )
        assert len(list(db.scalars(select(SignalEvent)))) == 2

        # Once the BTC signal hits TP, a new BTC signal may be created.
        evaluate_active_signals(db, "BTCUSDT", 104.0, 99.0, "candle-after-tp")
        btc = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "BTCUSDT"))
        assert btc.status == "CLOSED"
        assert json.loads(btc.reasons_json)["outcome"] == "TP"

        record_signal(
            db, "BTCUSDT", "SELL", ["15m", "30m"], ["New setup after TP"],
            "candle-5",
            {"entry": 100.0, "stop_loss": 102.0, "take_profit": 97.0},
            "signal-candle-5",
        )
        btc_events = list(db.scalars(
            select(SignalEvent).where(SignalEvent.symbol == "BTCUSDT")
            .order_by(SignalEvent.id)
        ))
        assert len(btc_events) == 2
        assert [event.status for event in btc_events] == ["CLOSED", "ACTIVE"]
        assert [event.side for event in btc_events] == ["BUY", "SELL"]
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_signal_outcomes_resolve_ambiguous_candles_conservatively_as_sl():
    from app.api.signals import evaluate_active_signals

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        plan = {"entry": 100.0, "stop_loss": 98.0, "take_profit": 104.0}
        current_mode = "TRADINGAGENTS_MULTI_AGENT_V8"
        record_signal(
            db, "TPTEST", "BUY", ["4h", "1h", "15m"], ["setup"],
            "signal-tp", plan, "candle-tp-1", strategy_mode=current_mode,
        )
        record_signal(
            db, "AMBTEST", "BUY", ["4h", "1h", "15m"], ["setup"],
            "signal-amb", plan, "candle-amb-1", strategy_mode=current_mode,
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
        assert amb_payload["outcome"] == "SL"
        assert amb_payload["realized_r"] == -1.0
        assert amb_payload["ambiguous_candle"] is True

        record_signal(
            db, "SLTEST", "BUY", ["4h", "1h", "15m"], ["setup"],
            "signal-sl", plan, "candle-sl-1", strategy_mode=current_mode,
        )
        evaluate_active_signals(db, "SLTEST", 101.0, 97.0, "candle-sl-2")
        sl_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "SLTEST"))
        assert json.loads(sl_row.reasons_json)["outcome"] == "SL"

        from app.api.signals import signal_performance

        stats = signal_performance(db)
        assert stats["completed"] == 3
        assert stats["wins"] == 1
        assert stats["losses"] == 2
        assert stats["ambiguous"] == 1
        assert abs(stats["win_rate_pct"] - (100 / 3)) < 1e-9
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()



def test_signal_creation_and_result_send_push_without_breaking_persistence(monkeypatch):
    from app.api.signals import evaluate_active_signals
    from app.services import push_notifications

    calls = []

    def fake_push(_db, **kwargs):
        calls.append(kwargs)
        return {"sent": 1, "failed": 0, "configured": 1}

    monkeypatch.setattr(
        push_notifications, "send_push_to_registered_devices", fake_push
    )
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
    from app.api.signals import evaluate_active_signals
    from app.services import push_notifications

    def failing_push(*_args, **_kwargs):
        raise RuntimeError("simulated FCM outage")

    monkeypatch.setattr(
        push_notifications, "send_push_to_registered_devices", failing_push
    )
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



def test_signal_creation_rejects_invalid_trade_plan():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        record_signal(
            db, "INVALIDPLAN", "BUY", ["15m", "30m"], ["setup"],
            "invalid-plan-1", {"entry": 100, "stop_loss": 101, "take_profit": 105},
        )
        record_signal(
            db, "MISSINGPLAN", "SELL", ["15m", "30m"], ["setup"],
            "missing-plan-1", None,
        )
        assert list(db.scalars(select(SignalEvent))) == []
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_manual_close_is_idempotent():
    from app.api.signals import close_signal

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        record_signal(
            db, "MANUALTEST", "BUY", ["15m", "30m"], ["setup"],
            "manual-signal-1",
            {"entry": 100, "stop_loss": 98, "take_profit": 103},
        )
        event = db.scalar(select(SignalEvent))
        first = close_signal(event.id, db)
        second = close_signal(event.id, db)
        assert first.status == "CLOSED"
        assert second.status == "CLOSED"
        assert second.outcome == "MANUAL"
        assert len(list(db.scalars(select(SignalNotification)))) == 2
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_v8_inbox_filters_and_returns_linked_signal_details():
    from app.api.signals import list_notifications

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()

        record_signal(
            db, "V8INBOX", "BUY", ["1h", "30m", "15m"], ["Aligned V8 setup"],
            "v8-inbox-candle", {
                "entry": 100, "stop_loss": 98, "take_profit": 103,
                "take_profit_1": 101, "take_profit_2": 102,
                "take_profit_3": 103,
                "confirmation_score": "3/3 higher-timeframe alignment",
                "confidence_note": "Konfirmasi timeframe; bukan probabilitas win rate.",
            },
            "v8-inbox-candle", strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
        )
        record_signal(
            db, "LEGACYINBOX", "SELL", ["1h", "15m"], ["Legacy setup"],
            "legacy-inbox-candle", {"entry": 100, "stop_loss": 102, "take_profit": 97},
            "legacy-inbox-candle", strategy_mode="LEGACY_UNVERSIONED",
        )

        notifications = list_notifications(
            unread_only=False,
            limit=50,
            strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
            db=db,
        )
        assert len(notifications) == 1
        item = notifications[0]
        assert item.signal_id is not None
        assert item.strategy_mode == "TRADINGAGENTS_MULTI_AGENT_V8"
        assert item.symbol == "V8INBOX"
        assert item.side == "BUY"
        assert item.signal_status == "ACTIVE"
        assert item.entry == 100
        assert item.stop_loss == 98
        assert item.take_profit == 103
        assert item.take_profit_1 == 101
        assert item.take_profit_2 == 102
        assert item.take_profit_3 == 103
        assert item.confirmation_score == "3/3 higher-timeframe alignment"
        assert "bukan probabilitas" in item.confidence_note
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_v8_inbox_filters_before_pagination_when_legacy_history_is_large():
    from datetime import datetime, timedelta, timezone

    from app.api.signals import list_notifications, list_signals

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        now = datetime.now(timezone.utc)
        v8 = SignalEvent(
            dedupe_key="v8-old-page-test",
            symbol="V8PAGE",
            side="BUY",
            status="ACTIVE",
            timeframe_set="1h,30m,15m",
            reasons_json=json.dumps({
                "reasons": ["V8 setup"],
                "trade_plan": {"entry": 100, "stop_loss": 98, "take_profit": 103},
                "strategy_mode": "TRADINGAGENTS_MULTI_AGENT_V8",
            }),
            created_at=now - timedelta(minutes=500),
            updated_at=now - timedelta(minutes=500),
        )
        db.add(v8)
        db.flush()
        db.add(SignalNotification(
            signal_id=v8.id,
            title="V8 older signal",
            message="Persisted V8 notification",
            created_at=now - timedelta(minutes=500),
        ))
        for index in range(205):
            created = now - timedelta(minutes=204 - index)
            legacy = SignalEvent(
                dedupe_key=f"legacy-page-test-{index}",
                symbol=f"OLD{index:03d}",
                side="SELL",
                status="ACTIVE",
                timeframe_set="1h,15m",
                reasons_json=json.dumps({
                    "reasons": ["legacy"],
                    "trade_plan": {"entry": 100, "stop_loss": 102, "take_profit": 97},
                    "strategy_mode": "LEGACY_UNVERSIONED",
                }),
                created_at=created,
                updated_at=created,
            )
            db.add(legacy)
            db.flush()
            db.add(SignalNotification(
                signal_id=legacy.id,
                title="Legacy signal",
                message="Legacy notification",
                created_at=created,
            ))
        db.commit()

        inbox = list_notifications(
            unread_only=False, limit=10,
            strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8", db=db,
        )
        signals = list_signals(
            status="all", limit=10,
            strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8", db=db,
        )
        assert len(inbox) == 1
        assert inbox[0].symbol == "V8PAGE"
        assert len(signals) == 1
        assert signals[0]["symbol"] == "V8PAGE"
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_v8_decision_exposes_three_risk_based_targets_without_fake_win_probability():
    from app.services.analysis.tradingagents_market_context import finalize_v8_decision

    timeframe = {
        "side": "BUY",
        "entry": 100.0,
        "stop_loss": 98.0,
        "take_profit": 103.0,
        "reasons": ["Harga di atas MA40."],
    }
    market_context = {
        "symbol": "BTCUSDT",
        "timeframes": {
            "1h": dict(timeframe),
            "30m": dict(timeframe),
            "15m": dict(timeframe),
            "5m": dict(timeframe),
        },
    }
    result = finalize_v8_decision(
        "Buy",
        "Research supports a bullish setup.",
        {"market_report": "Bullish market structure."},
        market_context,
    )

    plan = result["trade_plan"]
    assert result["side"] == "BUY"
    assert plan["take_profit_1"] == 101.0
    assert plan["take_profit_2"] == 102.0
    assert plan["take_profit_3"] == 103.0
    assert plan["take_profit"] == plan["take_profit_3"]
    assert plan["confirmation_score"] == "3/3 higher-timeframe alignment"
    assert "bukan probabilitas win rate" in plan["confidence_note"]
