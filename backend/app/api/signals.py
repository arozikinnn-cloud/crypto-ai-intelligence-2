import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.signal_event import SignalEvent, SignalNotification
from app.schemas.signals import SignalEventResponse, SignalNotificationResponse

router = APIRouter(prefix="/signals", tags=["signal lifecycle and notifications"])


def record_signal(db: Session, symbol: str, side: str, intervals: list[str], reasons: list[str]) -> None:
    if side not in {"BUY", "SELL"}:
        return
    now = datetime.now(timezone.utc)
    timeframe_set = ",".join(intervals)
    dedupe_key = f"{symbol.upper()}:{timeframe_set}:{side}"
    active = db.scalar(select(SignalEvent).where(
        SignalEvent.dedupe_key == dedupe_key, SignalEvent.status == "ACTIVE"
    ))
    if active:
        active.updated_at = now
        db.commit()
        return
    event = SignalEvent(
        dedupe_key=dedupe_key,
        symbol=symbol.upper(),
        side=side,
        status="ACTIVE",
        timeframe_set=timeframe_set,
        reasons_json=json.dumps(reasons, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    db.add(event)
    db.flush()
    db.add(SignalNotification(
        signal_id=event.id,
        title=f"{symbol.upper()} {side} signal",
        message="; ".join(reasons),
        created_at=now,
    ))
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
    return [
        SignalEventResponse(
            id=row.id, symbol=row.symbol, side=row.side, status=row.status,
            timeframe_set=row.timeframe_set, reasons=json.loads(row.reasons_json),
            created_at=row.created_at, updated_at=row.updated_at,
        )
        for row in db.scalars(statement)
    ]


@router.get("/notifications", response_model=list[SignalNotificationResponse])
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(SignalNotification).order_by(SignalNotification.created_at.desc()).limit(limit)
    if unread_only:
        statement = statement.where(SignalNotification.read_at.is_(None))
    return [
        SignalNotificationResponse(
            id=row.id, signal_id=row.signal_id, title=row.title, message=row.message,
            read=row.read_at is not None, created_at=row.created_at,
        )
        for row in db.scalars(statement)
    ]


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
    return SignalEventResponse(
        id=row.id, symbol=row.symbol, side=row.side, status=row.status,
        timeframe_set=row.timeframe_set, reasons=json.loads(row.reasons_json),
        created_at=row.created_at, updated_at=row.updated_at,
    )
