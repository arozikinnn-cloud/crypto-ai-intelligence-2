import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.signal_event import SignalEvent, SignalNotification
from app.schemas.signals import SignalEventResponse, SignalNotificationResponse

router = APIRouter(prefix="/signals", tags=["signal lifecycle and notifications"])


def _event_payload(row: SignalEvent) -> dict:
    stored = json.loads(row.reasons_json)
    if isinstance(stored, dict):
        reasons = stored.get("reasons", [])
        plan = stored.get("trade_plan") or {}
        outcome = stored.get("outcome")
        return {
            "id": row.id, "symbol": row.symbol, "side": row.side,
            "status": row.status, "timeframe_set": row.timeframe_set,
            "reasons": reasons, "created_at": row.created_at,
            "updated_at": row.updated_at, "entry": plan.get("entry"),
            "stop_loss": plan.get("stop_loss"),
            "take_profit": plan.get("take_profit"),
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
    """Close tracked signals only when a later candle reaches TP or SL.

    If both levels are crossed inside one candle, mark the result ambiguous
    rather than guessing which level was hit first.
    """
    now = datetime.now(timezone.utc)
    rows = list(db.scalars(select(SignalEvent).where(
        SignalEvent.symbol == symbol.upper(),
        SignalEvent.status == "ACTIVE",
    )))
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
        if not all(isinstance(value, (int, float)) for value in (entry, stop, target)):
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
        if hit_stop and hit_target:
            outcome, realized_r = "AMBIGUOUS", None
        elif hit_stop:
            outcome, realized_r = "SL", -1.0
        else:
            outcome = "TP"
            realized_r = reward / risk if risk > 0 else None
        stored["outcome"] = outcome
        stored["realized_r"] = realized_r
        stored["closed_at"] = now.isoformat()
        row.reasons_json = json.dumps(stored, ensure_ascii=False)
        row.status = "CLOSED"
        row.updated_at = now
        db.add(SignalNotification(
            signal_id=row.id,
            title=f"{row.symbol} {outcome}",
            message=("Hasil sinyal otomatis: " + outcome +
                     (f" ({realized_r:.2f}R)" if realized_r is not None else
                      " — urutan TP/SL tidak dapat dipastikan pada candle yang sama.")),
            created_at=now,
        ))
    db.commit()


def record_signal(
    db: Session,
    symbol: str,
    side: str,
    intervals: list[str],
    reasons: list[str],
    candle_timestamp: str,
    trade_plan: dict | None = None,
    signal_candle_timestamp: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    timeframe_set = ",".join(intervals)
    active_rows = list(db.scalars(select(SignalEvent).where(
        SignalEvent.symbol == symbol.upper(),
        SignalEvent.timeframe_set == timeframe_set,
        SignalEvent.status == "ACTIVE",
    )))
    if side in {"BUY", "SELL"}:
        same_side = next((row for row in active_rows if row.side == side), None)
        for row in active_rows:
            if row.side != side:
                row.status = "INVALIDATED"
                row.updated_at = now
        if same_side:
            same_side.updated_at = now
            db.commit()
            return
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
            }, ensure_ascii=False),
            created_at=now, updated_at=now,
        )
        db.add(event)
        db.flush()
        db.add(SignalNotification(
            signal_id=event.id, title=f"{symbol.upper()} {side} signal",
            message="; ".join(reasons), created_at=now,
        ))
        db.commit()
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
            if entry is not None: details.append(f"Entry: {entry}")
            if stop is not None: details.append(f"SL: {stop}")
            if target is not None: details.append(f"TP: {target}")
            if rr is not None: details.append(f"R:R 1:{float(rr):.2f}")
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
            import logging
            logging.getLogger(__name__).exception("FCM signal push failed; signal remains saved")
    else:
        for row in active_rows:
            row.status = "INVALIDATED"
            row.updated_at = now
    db.commit()


@router.get("", response_model=list[SignalEventResponse])
def list_signals(
    status: str = Query(default="ACTIVE", pattern="^(ACTIVE|CLOSED|INVALIDATED|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(SignalEvent).order_by(SignalEvent.created_at.desc()).limit(limit)
    if status != "all":
        statement = statement.where(SignalEvent.status == status)
    return [_event_payload(row) for row in db.scalars(statement)]


@router.get("/performance")
def signal_performance(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(SignalEvent)))
    completed = []
    for row in rows:
        payload = _event_payload(row)
        if payload.get("outcome") in {"TP", "SL"}:
            completed.append(payload)
    wins = sum(item["outcome"] == "TP" for item in completed)
    losses = sum(item["outcome"] == "SL" for item in completed)
    total_r = sum(float(item.get("realized_r") or 0) for item in completed)
    return {
        "total_signals": len(rows),
        "active": sum(row.status == "ACTIVE" for row in rows),
        "invalidated": sum(row.status == "INVALIDATED" for row in rows),
        "completed": len(completed),
        "wins": wins,
        "losses": losses,
        "ambiguous": sum(
            _event_payload(row).get("outcome") == "AMBIGUOUS" for row in rows
        ),
        "win_rate_pct": (wins / len(completed) * 100) if completed else None,
        "total_realized_r": round(total_r, 4),
        "method_note": (
            "WR dihitung hanya dari sinyal dengan TP/SL terkonfirmasi. "
            "Jika TP dan SL tersentuh pada candle yang sama, hasil dikecualikan."
        ),
    }


@router.get("/notifications", response_model=list[SignalNotificationResponse])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = (
        select(SignalNotification)
        .order_by(SignalNotification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        statement = statement.where(SignalNotification.read_at.is_(None))
    return [SignalNotificationResponse(
        id=row.id, signal_id=row.signal_id, title=row.title, message=row.message,
        read=row.read_at is not None, created_at=row.created_at,
    ) for row in db.scalars(statement)]


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
    row.status = "CLOSED"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return SignalEventResponse(**_event_payload(row))
