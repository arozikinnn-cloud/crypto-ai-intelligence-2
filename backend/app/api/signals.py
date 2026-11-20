import json
import logging
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.signal_event import SignalEvent, SignalNotification
from app.schemas.signals import SignalEventResponse, SignalNotificationResponse

router = APIRouter(prefix="/signals", tags=["signal lifecycle and notifications"])
logger = logging.getLogger(__name__)
CURRENT_STRATEGY_MODE = "TRADINGAGENTS_MULTI_AGENT_V8"


def _valid_trade_plan(side: str, plan: dict | None) -> bool:
    if not isinstance(plan, dict):
        return False
    values = [plan.get("entry"), plan.get("stop_loss"), plan.get("take_profit")]
    if not all(
        isinstance(value, (int, float)) and math.isfinite(float(value))
        for value in values
    ):
        return False
    entry, stop, target = (float(value) for value in values)
    if side == "BUY":
        return stop < entry < target
    if side == "SELL":
        return target < entry < stop
    return False


def _event_payload(row: SignalEvent) -> dict:
    try:
        stored = json.loads(row.reasons_json)
    except (TypeError, json.JSONDecodeError):
        stored = {"reasons": ["Data alasan sinyal lama tidak dapat dibaca."]}
    if isinstance(stored, dict):
        reasons = list(stored.get("reasons", []))
        if stored.get("invalidation_reason"):
            reasons.append("Alasan invalidasi: " + stored["invalidation_reason"])
        if stored.get("close_reason"):
            reasons.append("Alasan penutupan: " + stored["close_reason"])
        plan = stored.get("trade_plan") or {}
        outcome = stored.get("outcome")
        strategy_mode = stored.get("strategy_mode")
        if not strategy_mode or strategy_mode == "LEGACY_UNVERSIONED":
            # The first live signals from this strategy were created before
            # strategy_mode was persisted. Their new decision-reason prefix
            # lets us classify them without mixing older EMA/legacy signals.
            strategy_mode = (
                CURRENT_STRATEGY_MODE
                if any(
                    isinstance(reason, str) and reason.startswith("H1 memberi bias ")
                    for reason in reasons
                )
                else "LEGACY_UNVERSIONED"
            )
        entry = plan.get("entry")
        stop = plan.get("stop_loss")
        target = plan.get("take_profit")
        is_current_strategy = strategy_mode == CURRENT_STRATEGY_MODE
        risk = (
            abs(float(entry) - float(stop))
            if isinstance(entry, (int, float))
            and isinstance(stop, (int, float))
            and math.isfinite(float(entry))
            and math.isfinite(float(stop))
            else None
        )
        direction = 1.0 if row.side == "BUY" else -1.0
        tp1 = plan.get("take_profit_1")
        tp2 = plan.get("take_profit_2")
        tp3 = plan.get("take_profit_3") or target
        if is_current_strategy and risk is not None and risk > 0:
            tp1 = tp1 if tp1 is not None else float(entry) + direction * risk * 0.5
            tp2 = tp2 if tp2 is not None else float(entry) + direction * risk
        confirmation_score = plan.get("confirmation_score")
        confidence_note = plan.get("confidence_note")
        if is_current_strategy:
            confirmation_score = confirmation_score or "3/3 higher-timeframe alignment"
            confidence_note = confidence_note or (
                "Konfirmasi arah H1, M30, dan M15; bukan probabilitas win rate "
                "atau jaminan hasil."
            )
        return {
            "id": row.id, "symbol": row.symbol, "side": row.side,
            "status": row.status, "timeframe_set": row.timeframe_set,
            "reasons": reasons, "created_at": row.created_at,
            "updated_at": row.updated_at, "entry": entry,
            "stop_loss": stop,
            "take_profit": target,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "take_profit_3": tp3,
            "confirmation_score": confirmation_score,
            "confidence_note": confidence_note,
            "strategy_mode": strategy_mode,
            "ambiguous_candle": bool(stored.get("ambiguous_candle")),
            "outcome": outcome, "realized_r": stored.get("realized_r"),
            "closed_at": stored.get("closed_at"),
        }
    return {
        "id": row.id, "symbol": row.symbol, "side": row.side,
        "status": row.status, "timeframe_set": row.timeframe_set,
        "reasons": stored if isinstance(stored, list) else [],
        "created_at": row.created_at, "updated_at": row.updated_at,
    }


def evaluate_active_signals(
    db: Session, symbol: str, candle_high: float, candle_low: float,
    candle_timestamp: str,
) -> None:
    """Evaluate active signals against a later, fully closed market candle.

    If TP and SL are both crossed in one OHLC candle, conservatively record SL:
    OHLC data cannot establish intrabar order, and performance must not overstate.
    """
    now = datetime.now(timezone.utc)
    rows = list(db.scalars(select(SignalEvent).where(
        SignalEvent.symbol == symbol.upper(),
        SignalEvent.status == "ACTIVE",
    ).with_for_update(skip_locked=True)))
    closed_signals: list[tuple[SignalEvent, str, float | None]] = []
    for row in rows:
        try:
            stored = json.loads(row.reasons_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(stored, dict):
            continue
        if stored.get("signal_candle_timestamp") == candle_timestamp:
            continue
        plan = stored.get("trade_plan") or {}
        entry = plan.get("entry")
        stop = plan.get("stop_loss")
        target = plan.get("take_profit")
        if not _valid_trade_plan(row.side, plan):
            continue
        if row.side == "BUY":
            hit_stop, hit_target = candle_low <= stop, candle_high >= target
            risk = entry - stop
            reward = target - entry
        else:
            hit_stop, hit_target = candle_high >= stop, candle_low <= target
            risk = stop - entry
            reward = entry - target
        if not hit_stop and not hit_target:
            continue
        ambiguous = hit_stop and hit_target
        if hit_stop:
            outcome, realized_r = "SL", -1.0
        else:
            outcome = "TP"
            realized_r = reward / risk if risk > 0 else None
        stored["ambiguous_candle"] = ambiguous
        stored["outcome"] = outcome
        stored["realized_r"] = realized_r
        stored["closed_at"] = now.isoformat()
        stored["close_candle_timestamp"] = candle_timestamp
        if ambiguous:
            stored["close_reason"] = (
                "TP dan SL tersentuh dalam candle yang sama; hasil dicatat "
                "konservatif sebagai SL karena urutan intrabar tidak tersedia."
            )
        else:
            level = "stop-loss" if outcome == "SL" else "take-profit"
            stored["close_reason"] = f"Candle tertutup menyentuh {level}."
        row.reasons_json = json.dumps(stored, ensure_ascii=False)
        row.status = "CLOSED"
        row.updated_at = now
        message = (
            f"Hasil sinyal otomatis: {outcome}"
            + (f" ({realized_r:.2f}R)" if realized_r is not None else "")
            + (" — TP dan SL satu candle, dicatat konservatif sebagai SL." if ambiguous else "")
        )
        db.add(SignalNotification(
            signal_id=row.id,
            title=f"{row.symbol} {outcome}",
            message=message,
            created_at=now,
        ))
        closed_signals.append((row, outcome, realized_r))
    db.commit()

    # Deliver TP/SL results to devices too; persist the result first so an FCM
    # outage cannot roll back the signal lifecycle or its performance history.
    for row, outcome, realized_r in closed_signals:
        try:
            from app.services.push_notifications import send_push_to_registered_devices

            stored = json.loads(row.reasons_json)
            plan = stored.get("trade_plan") or {}
            send_push_to_registered_devices(
                db,
                title=f"{row.symbol} {outcome}",
                body=(
                    f"Hasil sinyal {row.side}: {outcome}"
                    + (f" ({realized_r:.2f}R)" if realized_r is not None else "")
                ),
                data={
                    "type": "trade_result",
                    "signal_id": str(row.id),
                    "symbol": row.symbol,
                    "side": row.side,
                    "outcome": outcome,
                    "entry": str(plan.get("entry") or ""),
                    "stop_loss": str(plan.get("stop_loss") or ""),
                    "take_profit": str(plan.get("take_profit") or ""),
                    "realized_r": str(realized_r if realized_r is not None else ""),
                },
            )
        except Exception:
            logger.exception("FCM result push failed; outcome remains saved")


def record_signal(
    db: Session,
    symbol: str,
    side: str,
    intervals: list[str],
    reasons: list[str],
    candle_timestamp: str,
    trade_plan: dict | None = None,
    signal_candle_timestamp: str | None = None,
    strategy_mode: str | None = None,
) -> None:
    if side not in {"BUY", "SELL"} or not _valid_trade_plan(side, trade_plan):
        return
    now = datetime.now(timezone.utc)
    timeframe_set = ",".join(intervals)
    # Keep one active trade thesis per symbol. A validated V8 thesis may
    # explicitly supersede a legacy thesis; legacy or duplicate analyses cannot
    # replace an active V8 thesis or bypass the symbol-wide uniqueness lock.
    active_rows = list(db.scalars(select(SignalEvent).where(
        SignalEvent.symbol == symbol.upper(),
        SignalEvent.status == "ACTIVE",
    )))
    if side in {"BUY", "SELL"} and active_rows:
        active_v8 = [
            row for row in active_rows
            if _event_payload(row).get("strategy_mode") == CURRENT_STRATEGY_MODE
        ]
        if strategy_mode == CURRENT_STRATEGY_MODE and not active_v8:
            # A fully validated V8 multi-agent thesis takes precedence over
            # legacy technical signals. Invalidate the old thesis explicitly
            # so the symbol-wide active-signal uniqueness invariant is kept.
            for previous in active_rows:
                try:
                    previous_payload = json.loads(previous.reasons_json)
                except (TypeError, json.JSONDecodeError):
                    previous_payload = {"reasons": []}
                if not isinstance(previous_payload, dict):
                    previous_payload = {"reasons": []}
                previous_payload["invalidation_reason"] = (
                    "Digantikan oleh sinyal TradingAgents V8 yang lolos "
                    "validasi multi-agent dan data Bitget terbaru."
                )
                previous.reasons_json = json.dumps(
                    previous_payload, ensure_ascii=False
                )
                previous.status = "INVALIDATED"
                previous.updated_at = now
                db.add(SignalNotification(
                    signal_id=previous.id,
                    title=f"{previous.symbol} legacy signal invalidated",
                    message=previous_payload["invalidation_reason"],
                    created_at=now,
                ))
        else:
            # Legacy signals cannot replace an active V8 signal, and duplicate
            # signals from the same strategy remain blocked until TP/SL.
            db.commit()
            return
    if side in {"BUY", "SELL"}:
        dedupe_key = f"{symbol.upper()}:{timeframe_set}:{side}:{candle_timestamp}"
        previous_event = db.scalar(
            select(SignalEvent).where(SignalEvent.dedupe_key == dedupe_key)
        )
        if previous_event is not None:
            db.commit()
            return
        event = SignalEvent(
            dedupe_key=dedupe_key, symbol=symbol.upper(), side=side, status="ACTIVE",
            timeframe_set=timeframe_set,
            reasons_json=json.dumps({
                "reasons": reasons, "trade_plan": trade_plan or {},
                "outcome": None, "realized_r": None, "closed_at": None,
                "signal_candle_timestamp": signal_candle_timestamp,
                "strategy_mode": strategy_mode or "LEGACY_UNVERSIONED",
            }, ensure_ascii=False),
            created_at=now, updated_at=now,
        )
        db.add(event)
        try:
            db.flush()
            db.add(SignalNotification(
                signal_id=event.id, title=f"{symbol.upper()} {side} signal",
                message="; ".join(reasons), created_at=now,
            ))
            db.commit()
        except IntegrityError:
            # Partial unique index is the final guard against concurrent creates.
            db.rollback()
            return
        # Push delivery is best-effort: a Firebase outage must never fail analysis.
        try:
            from app.services.push_notifications import send_push_to_registered_devices

            plan = trade_plan or {}
            entry = plan.get("entry")
            stop = plan.get("stop_loss")
            target = plan.get("take_profit")
            rr = plan.get("risk_reward") or plan.get("rr")
            if rr is None and all(isinstance(v, (int, float)) for v in (entry, stop, target)):
                risk = abs(float(entry) - float(stop))
                reward = abs(float(target) - float(entry))
                rr = reward / risk if risk > 0 else None
            details = []
            if entry is not None:
                details.append(f"Entry: {entry}")
            if stop is not None:
                details.append(f"SL: {stop}")
            if target is not None:
                details.append(f"TP: {target}")
            if rr is not None:
                details.append(f"R:R 1:{float(rr):.2f}")
            body = " • ".join(details) if details else "; ".join(reasons[:3])
            send_push_to_registered_devices(
                db,
                title=f"{symbol.upper()} {side} signal",
                body=body or "Sinyal trading baru terdeteksi.",
                data={
                    "type": "trade_signal", "signal_id": str(event.id),
                    "symbol": symbol.upper(), "side": side,
                    "entry": str(entry or ""), "stop_loss": str(stop or ""),
                    "take_profit": str(target or ""), "risk_reward": str(rr or ""),
                },
            )
        except Exception:
            logger.exception("FCM signal push failed; signal remains saved")
    else:
        # NO TRADE means no new setup; it never changes an existing active signal.
        # The symbol remains locked until its tracked TP/SL outcome is recorded.
        pass
    db.commit()


@router.get("", response_model=list[SignalEventResponse])
def list_signals(
    status: str = Query(default="ACTIVE", pattern="^(ACTIVE|CLOSED|INVALIDATED|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    strategy_mode: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    statement = select(SignalEvent).order_by(SignalEvent.created_at.desc())
    if status != "all":
        statement = statement.where(SignalEvent.status == status)
    if strategy_mode:
        # Filter in SQL before limiting so old/legacy rows cannot crowd V8
        # signals out of the requested page.
        statement = statement.where(
            SignalEvent.reasons_json.contains(
                f'"strategy_mode":"{strategy_mode}"', autoescape=True
            )
        )
    payloads = [_event_payload(row) for row in db.scalars(statement.limit(limit))]
    if strategy_mode:
        payloads = [
            item for item in payloads if item.get("strategy_mode") == strategy_mode
        ]
    return payloads


@router.get("/performance")
def signal_performance(db: Session = Depends(get_db)):
    current_mode = CURRENT_STRATEGY_MODE
    payloads = [_event_payload(row) for row in db.scalars(select(SignalEvent))]
    current = [
        item for item in payloads
        if item.get("strategy_mode") == current_mode
    ]
    legacy = [
        item for item in payloads
        if item.get("strategy_mode") != current_mode
    ]

    def summarize(items: list[dict]) -> dict:
        completed = [
            item for item in items
            if item.get("outcome") in {"TP", "SL"}
        ]
        wins = sum(item["outcome"] == "TP" for item in completed)
        losses = sum(item["outcome"] == "SL" for item in completed)
        total_r = sum(float(item.get("realized_r") or 0) for item in completed)
        return {
            "total_signals": len(items),
            "active": sum(item.get("status") == "ACTIVE" for item in items),
            "invalidated": sum(item.get("status") == "INVALIDATED" for item in items),
            "completed": len(completed),
            "wins": wins,
            "losses": losses,
            "ambiguous": sum(bool(item.get("ambiguous_candle")) for item in items),
            "win_rate_pct": (wins / len(completed) * 100) if completed else None,
            "total_realized_r": round(total_r, 4),
        }

    current_stats = summarize(current)
    legacy_stats = summarize(legacy)
    return {
        **current_stats,
        "current_strategy_mode": current_mode,
        "legacy_total_signals": legacy_stats["total_signals"],
        "legacy_completed": legacy_stats["completed"],
        "legacy_wins": legacy_stats["wins"],
        "legacy_losses": legacy_stats["losses"],
        "legacy_win_rate_pct": legacy_stats["win_rate_pct"],
        "method_note": (
            "Statistik utama hanya menghitung sinyal TradingAgents V8 yang telah "
            "melewati validasi data Bitget Futures dan konfirmasi multi-timeframe. "
            "Sinyal strategi lama dipisahkan sebagai riwayat legacy dan tidak dicampur. "
            "WR dihitung hanya dari sinyal TP/SL terkonfirmasi; TP dan SL pada "
            "candle yang sama dihitung sebagai SL secara konservatif."
        ),
    }


@router.get("/notifications", response_model=list[SignalNotificationResponse])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    strategy_mode: str | None = Query(default=None, max_length=80),
    db: Session = Depends(get_db),
):
    # Return the notification and its originating signal as one joined record.
    # Signal Inbox can therefore show exactly the same strategy, direction,
    # levels, and lifecycle state as Signal Center.
    statement = (
        select(SignalNotification, SignalEvent)
        .outerjoin(SignalEvent, SignalNotification.signal_id == SignalEvent.id)
        .order_by(SignalNotification.created_at.desc())
    )
    if unread_only:
        statement = statement.where(SignalNotification.read_at.is_(None))
    if strategy_mode:
        # Apply strategy filtering before pagination; otherwise a busy legacy
        # inbox could hide every newer V8 notification behind the first 200.
        statement = statement.where(
            SignalEvent.reasons_json.contains(
                f'"strategy_mode":"{strategy_mode}"', autoescape=True
            )
        )
    statement = statement.limit(limit)

    items = []
    for notification, signal in db.execute(statement):
        payload = _event_payload(signal) if signal is not None else {}
        if strategy_mode and payload.get("strategy_mode") != strategy_mode:
            continue
        items.append(SignalNotificationResponse(
            id=notification.id,
            signal_id=notification.signal_id,
            title=notification.title,
            message=notification.message,
            read=notification.read_at is not None,
            created_at=notification.created_at,
            strategy_mode=payload.get("strategy_mode"),
            symbol=payload.get("symbol"),
            side=payload.get("side"),
            signal_status=payload.get("status"),
            entry=payload.get("entry"),
            stop_loss=payload.get("stop_loss"),
            take_profit=payload.get("take_profit"),
            take_profit_1=payload.get("take_profit_1"),
            take_profit_2=payload.get("take_profit_2"),
            take_profit_3=payload.get("take_profit_3"),
            confirmation_score=payload.get("confirmation_score"),
            confidence_note=payload.get("confidence_note"),
            signal_outcome=payload.get("outcome"),
            signal_realized_r=payload.get("realized_r"),
            signal_closed_at=payload.get("closed_at"),
            signal_created_at=payload.get("created_at"),
        ))
        if len(items) >= limit:
            break
    return items


@router.post("/notifications/{notification_id}/read", response_model=SignalNotificationResponse)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
    row = db.get(SignalNotification, notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    row.read_at = datetime.now(timezone.utc)
    db.commit()
    return SignalNotificationResponse(
        id=row.id, signal_id=row.signal_id, title=row.title, message=row.message,
        read=True, created_at=row.created_at,
    )


@router.post("/{signal_id}/close", response_model=SignalEventResponse)
def close_signal(signal_id: int, db: Session = Depends(get_db)):
    row = db.get(SignalEvent, signal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Signal not found.")
    if row.status != "ACTIVE":
        return SignalEventResponse(**_event_payload(row))
    now = datetime.now(timezone.utc)
    try:
        stored = json.loads(row.reasons_json)
    except (TypeError, json.JSONDecodeError):
        stored = {"reasons": []}
    stored["outcome"] = stored.get("outcome") or "MANUAL"
    stored["close_reason"] = "Manually closed by user."
    stored["closed_at"] = now.isoformat()
    row.reasons_json = json.dumps(stored, ensure_ascii=False)
    row.status = "CLOSED"
    row.updated_at = now
    db.add(SignalNotification(
        signal_id=row.id,
        title=f"{row.symbol} {row.side} manually closed",
        message="Sinyal ditutup secara manual oleh pengguna.",
        created_at=now,
    ))
    db.commit()
    return SignalEventResponse(**_event_payload(row))
