from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.liquidation_record import LiquidationRecord


def persist_liquidation_events(db: Session, events: list[dict]) -> int:
    if not events:
        return 0
    try:
        keys = [event["event_key"] for event in events]
        existing = set(
            db.scalars(
                select(LiquidationRecord.event_key).where(
                    LiquidationRecord.event_key.in_(keys)
                )
            ).all()
        )
        inserted = 0
        for event in events:
            if event["event_key"] in existing:
                continue
            db.add(LiquidationRecord(**event))
            existing.add(event["event_key"])
            inserted += 1
        db.commit()
        return inserted
    except Exception:
        db.rollback()
        raise


def read_liquidation_history(
    db: Session, symbol: str, hours: int = 24
) -> dict:
    normalized = symbol.upper().strip()
    if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
        raise ValueError("Invalid liquidation symbol.")
    if not 1 <= hours <= 168:
        raise ValueError("Hours must be between 1 and 168.")

    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.scalars(
        select(LiquidationRecord)
        .where(
            LiquidationRecord.symbol == normalized,
            LiquidationRecord.timestamp >= start,
        )
        .order_by(LiquidationRecord.timestamp)
    ).all()
    buckets = {}
    for row in rows:
        event_time = row.timestamp
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        minute = int(
            event_time.replace(second=0, microsecond=0).timestamp() * 1000
        )
        key = (minute, row.side)
        bucket = buckets.setdefault(
            key,
            {
                "bucket_start_time": minute,
                "side": row.side,
                "event_count": 0,
                "total_quantity": 0.0,
                "total_notional": 0.0,
                "min_price": row.price,
                "max_price": row.price,
            },
        )
        bucket["event_count"] += 1
        bucket["total_quantity"] += row.quantity
        bucket["total_notional"] += row.notional
        bucket["min_price"] = min(bucket["min_price"], row.price)
        bucket["max_price"] = max(bucket["max_price"], row.price)

    points = sorted(buckets.values(), key=lambda item: (item["bucket_start_time"], item["side"]))
    return {
        "symbol": normalized,
        "source_market": "binance_usdm_futures_force_order",
        "hours": hours,
        "event_count": len(rows),
        "points": points,
        "note": (
            "Agregasi berdasarkan event force-order yang berhasil diterima dan disimpan "
            "aplikasi. Binance membatasi stream force-order; data ini bukan total seluruh "
            "likuidasi pasar dan dapat memiliki gap saat collector terputus."
        ),
    }
