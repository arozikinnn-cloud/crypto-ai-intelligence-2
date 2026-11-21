import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.api.signals import (
    CURRENT_STRATEGY_MODE,
    evaluate_active_signals,
    record_signal,
    signal_performance,
)
from app.database.base import Base
from app.database.session import SessionLocal, engine
from app.models.agent_analysis_job import AgentAnalysisJob
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

        evaluate_active_signals(db, "TPTEST", 103.0, 100.5, "candle-tp-2")
        tp_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "TPTEST"))
        assert tp_row.status == "ACTIVE"
        evaluate_active_signals(db, "TPTEST", 105.0, 102.5, "candle-tp-3")
        tp_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "TPTEST"))
        assert tp_row.status == "ACTIVE"
        evaluate_active_signals(db, "TPTEST", 107.0, 103.0, "candle-tp-4")
        tp_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "TPTEST"))
        tp_payload = json.loads(tp_row.reasons_json)
        assert tp_row.status == "CLOSED"
        assert tp_payload["outcome"] == "WIN"
        assert tp_payload["realized_r"] == 1.54745

        # If TP and SL occur in one OHLC candle, do not guess the order.
        evaluate_active_signals(db, "AMBTEST", 105.0, 97.0, "candle-amb-2")
        amb_row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "AMBTEST"))
        amb_payload = json.loads(amb_row.reasons_json)
        assert amb_row.status == "CLOSED"
        assert amb_payload["outcome"] == "SL"
        assert amb_payload["realized_r"] == -1.1485
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

        signal_candle = datetime.now(timezone.utc).isoformat()
        later_candle = (
            datetime.now(timezone.utc) + timedelta(minutes=15)
        ).isoformat()
        record_signal(
            db, "V8INBOX", "BUY", ["1h", "30m", "15m"], ["Aligned V8 setup"],
            signal_candle, {
                "entry": 100, "stop_loss": 98, "take_profit": 103,
                "take_profit_1": 101, "take_profit_2": 102,
                "take_profit_3": 103,
                "confirmation_score": "3/3 higher-timeframe alignment",
                "confidence_note": "Konfirmasi timeframe; bukan probabilitas win rate.",
            },
            signal_candle, strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
        )
        record_signal(
            db, "LEGACYINBOX", "SELL", ["1h", "15m"], ["Legacy setup"],
            "legacy-inbox-candle", {"entry": 100, "stop_loss": 102, "take_profit": 97},
            "legacy-inbox-candle", strategy_mode="LEGACY_UNVERSIONED",
        )

        from app.api.signals import evaluate_active_signals
        evaluate_active_signals(
            db, "V8INBOX", candle_high=104, candle_low=99,
            candle_timestamp=later_candle,
        )
        notifications = list_notifications(
            unread_only=False,
            limit=50,
            strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
            db=db,
        )
        assert len(notifications) == 2
        item = notifications[0]
        assert item.signal_id is not None
        assert item.strategy_mode == "TRADINGAGENTS_MULTI_AGENT_V8"
        assert item.symbol == "V8INBOX"
        assert item.side == "BUY"
        assert item.signal_status == "CLOSED"
        assert item.signal_outcome == "WIN"
        assert item.signal_realized_r == 0.34925
        assert item.signal_closed_at is not None
        assert item.entry == 100
        assert item.stop_loss == 98
        assert item.take_profit == 106
        assert item.take_profit_1 == 102
        assert item.take_profit_2 == 104
        assert item.take_profit_3 == 106
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
        assert inbox[0].signal_id == signals[0]["id"]
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
        "collected_at": datetime.now(timezone.utc).isoformat(),
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
    assert plan["take_profit_1"] == 102.0
    assert plan["take_profit_2"] == 104.0
    assert plan["take_profit_3"] == 106.0
    assert plan["take_profit"] == plan["take_profit_3"]
    assert plan["confirmation_score"] == "3/3 higher-timeframe alignment"
    assert "bukan probabilitas win rate" in plan["confidence_note"]
    assert any(
        "Level Entry/SL/TP final mengikuti candle tertutup Bitget Futures" in reason
        for reason in result["reasons"]
    )


def test_validated_v8_signal_replaces_legacy_active_signal_and_legacy_cannot_replace_v8():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()

        record_signal(
            db, "PRIORITYTEST", "SELL", ["1h", "15m"], ["Legacy bearish setup"],
            "legacy-priority-candle",
            {"entry": 100, "stop_loss": 102, "take_profit": 97},
            "legacy-priority-candle",
            strategy_mode="ICHIMOKU_RSI16_MA40_H1_M15_M5",
        )
        legacy = db.scalar(select(SignalEvent).where(
            SignalEvent.symbol == "PRIORITYTEST"
        ))
        assert legacy.status == "ACTIVE"

        record_signal(
            db, "PRIORITYTEST", "BUY", ["1h", "30m", "15m", "5m"],
            ["Validated TradingAgents V8 bullish setup"],
            "v8-priority-candle",
            {"entry": 100, "stop_loss": 98, "take_profit": 103},
            "v8-priority-candle",
            strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
        )
        rows = list(db.scalars(select(SignalEvent).where(
            SignalEvent.symbol == "PRIORITYTEST"
        ).order_by(SignalEvent.id)))
        assert len(rows) == 2
        assert rows[0].status == "INVALIDATED"
        assert "Digantikan oleh sinyal TradingAgents V8" in json.loads(
            rows[0].reasons_json
        )["invalidation_reason"]
        assert rows[1].status == "ACTIVE"
        assert rows[1].side == "BUY"

        # A later legacy analysis must not supersede the active validated V8 thesis.
        record_signal(
            db, "PRIORITYTEST", "SELL", ["1h", "15m"], ["New legacy reversal"],
            "legacy-after-v8-candle",
            {"entry": 100, "stop_loss": 102, "take_profit": 97},
            "legacy-after-v8-candle",
            strategy_mode="ICHIMOKU_RSI16_MA40_H1_M15_M5",
        )
        final_rows = list(db.scalars(select(SignalEvent).where(
            SignalEvent.symbol == "PRIORITYTEST"
        ).order_by(SignalEvent.id)))
        assert len(final_rows) == 2
        assert final_rows[1].status == "ACTIVE"
        assert final_rows[1].side == "BUY"
        assert any(
            "legacy signal invalidated" in item.title
            for item in db.scalars(select(SignalNotification))
        )
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()


def test_worker_recovers_missing_signal_from_recent_completed_job():
    from agent_worker import persist_recent_completed_v8_signals

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.execute(delete(AgentAnalysisJob))
        db.commit()
        now = datetime.now(timezone.utc)
        result = {
            "side": "BUY",
            "reasons": ["V8 multi-agent and Bitget timeframes aligned."],
            "trade_plan": {
                "entry": 100, "stop_loss": 98, "take_profit": 103,
                "take_profit_1": 101, "take_profit_2": 102,
                "take_profit_3": 103,
                "confirmation_score": "3/3 higher-timeframe alignment",
                "confidence_note": "Not a win-rate probability.",
            },
            "market_context": {
                "collected_at": now.isoformat(),
                "timeframes": {
                    "15m": {"candle_close_time": now.isoformat()},
                },
            },
        }
        db.add(AgentAnalysisJob(
            symbol="RECOVERYTEST",
            ticker="RECOVERY-USD",
            status="COMPLETED",
            created_at=now,
            started_at=now,
            completed_at=now,
            result_json=json.dumps(result),
        ))
        db.commit()

        checked = persist_recent_completed_v8_signals(session_factory=SessionLocal)
        assert checked == 1
        signal = db.scalar(select(SignalEvent).where(
            SignalEvent.symbol == "RECOVERYTEST"
        ))
        assert signal is not None
        assert signal.status == "ACTIVE"
        assert signal.side == "BUY"
        payload = json.loads(signal.reasons_json)
        assert payload["trade_plan"]["take_profit_1"] == 102
        assert payload["strategy_mode"] == "TRADINGAGENTS_MULTI_AGENT_V8"
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.execute(delete(AgentAnalysisJob))
        db.commit()
        db.close()


def test_v8_surfaces_soft_analyst_conflicts_and_blocks_final_plan_conflicts():
    from app.services.analysis.tradingagents_market_context import finalize_v8_decision

    timeframe = {
        "side": "SELL",
        "entry": 100.0,
        "stop_loss": 102.0,
        "take_profit": 97.0,
        "reasons": ["Harga di bawah MA40."],
    }
    context = {
        "symbol": "BTCUSDT",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": {
            "1h": dict(timeframe),
            "30m": dict(timeframe),
            "15m": dict(timeframe),
            "5m": dict(timeframe),
        },
    }
    soft_conflict = finalize_v8_decision(
        "Sell",
        "Rating: Sell",
        {
            "sentiment_report": "**Overall Sentiment:** **Bullish**",
            "investment_plan": "**Recommendation**: Sell",
            "trader_investment_plan": "**Action**: Sell",
            "final_trade_decision": "**Rating**: Sell",
        },
        context,
    )
    assert soft_conflict["side"] == "SELL"
    assert any(
        "sentiment_report=BUY" in reason for reason in soft_conflict["reasons"]
    )

    hard_conflict = finalize_v8_decision(
        "Sell",
        "Rating: Sell",
        {
            "investment_plan": "**Recommendation**: Buy",
            "trader_investment_plan": "**Action**: Sell",
            "final_trade_decision": "**Rating**: Sell",
        },
        context,
    )
    assert hard_conflict["side"] == "NO TRADE"
    assert hard_conflict["trade_plan"] is None
    assert any("Konflik keputusan final" in reason for reason in hard_conflict["reasons"])


def test_v8_blocks_signal_when_bitget_market_snapshot_is_stale():
    from app.services.analysis.tradingagents_market_context import finalize_v8_decision

    timeframe = {
        "side": "BUY",
        "entry": 100.0,
        "stop_loss": 98.0,
        "take_profit": 103.0,
        "reasons": ["Harga di atas MA40."],
    }
    context = {
        "symbol": "BTCUSDT",
        "collected_at": (
            datetime.now(timezone.utc) - timedelta(minutes=30)
        ).isoformat(),
        "timeframes": {
            "1h": dict(timeframe),
            "30m": dict(timeframe),
            "15m": dict(timeframe),
            "5m": dict(timeframe),
        },
    }
    result = finalize_v8_decision("Buy", "Rating: Buy", {}, context)
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None
    assert any("Data Bitget tidak cukup baru" in reason for reason in result["reasons"])


def test_v8_signal_uses_partial_tp_ladder_and_counts_be_stop_as_win():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        record_signal(
            db,
            "BTCUSDT",
            "BUY",
            ["1h", "30m", "15m", "5m"],
            ["V8 multi-agent confirmation"],
            "v8-candle-1",
            {"entry": 100.0, "stop_loss": 98.0, "take_profit": 103.0},
            signal_candle_timestamp="v8-signal-candle-1",
            strategy_mode=CURRENT_STRATEGY_MODE,
        )
        row = db.scalar(select(SignalEvent).where(SignalEvent.symbol == "BTCUSDT"))
        stored = json.loads(row.reasons_json)
        plan = stored["trade_plan"]
        assert plan["take_profit_1"] == 102.0
        assert plan["take_profit_2"] == 104.0
        assert plan["take_profit_3"] == 106.0
        assert plan["take_profit"] == 106.0

        evaluate_active_signals(db, "BTCUSDT", 102.2, 100.5, "v8-candle-2")
        db.refresh(row)
        stored = json.loads(row.reasons_json)
        assert row.status == "ACTIVE"
        assert stored["lifecycle"]["remaining_position_pct"] == 50.0
        assert stored["realized_r"] == 0.38675

        evaluate_active_signals(db, "BTCUSDT", 101.0, 99.9, "v8-candle-3")
        db.refresh(row)
        stored = json.loads(row.reasons_json)
        assert row.status == "CLOSED"
        assert stored["outcome"] == "WIN"
        assert stored["realized_r"] == 0.34925
        assert stored["lifecycle"]["closed_position_pct"] == 100.0
        performance = signal_performance(db)
        assert performance["wins"] == 1
        assert performance["losses"] == 0
        assert performance["breakeven"] == 0
    finally:
        db.rollback()
        db.execute(delete(SignalNotification))
        db.execute(delete(SignalEvent))
        db.commit()
        db.close()
