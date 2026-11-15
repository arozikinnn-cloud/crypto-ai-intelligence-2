from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cvd_bucket import CvdBucket
from app.models.cvd_collector_state import CvdCollectorState


def persist_aggtrade_events(db: Session, symbol: str, events: list[dict]) -> int:
    """Persist a batch once, deduplicating by Binance aggregate-trade ID."""
    normalized = symbol.upper()
    if not events:
        return 0

    try:
        state = db.scalar(
            select(CvdCollectorState)
            .where(CvdCollectorState.symbol == normalized)
            .with_for_update()
        )
        if state is None:
            state = CvdCollectorState(
                symbol=normalized,
                last_trade_id=-1,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(state)
            db.flush()

        last_id = state.last_trade_id
        accepted = sorted(
            (event for event in events if event["trade_id"] > last_id),
            key=lambda event: event["trade_id"],
        )
        if not accepted:
            db.rollback()
            return 0

        buckets = defaultdict(
            lambda: {"buy_volume": 0.0, "sell_volume": 0.0, "delta": 0.0, "trade_count": 0}
        )
        for event in accepted:
            bucket_time = datetime.fromtimestamp(
                event["timestamp"] // 60_000 * 60 / 1000, tz=timezone.utc
            )
            bucket = buckets[bucket_time]
            quantity = float(event["quantity"])
            if event["buyer_is_maker"]:
                bucket["sell_volume"] += quantity
                bucket["delta"] -= quantity
            else:
                bucket["buy_volume"] += quantity
                bucket["delta"] += quantity
            bucket["trade_count"] += 1

        for bucket_time, values in buckets.items():
            row = db.scalar(
                select(CvdBucket).where(
                    CvdBucket.symbol == normalized,
                    CvdBucket.source_market == "binance_spot_aggtrades",
                    CvdBucket.bucket_start_time == bucket_time,
                )
            )
            if row is None:
                db.add(
                    CvdBucket(
                        symbol=normalized,
                        source_market="binance_spot_aggtrades",
                        bucket_start_time=bucket_time,
                        **values,
                    )
                )
            else:
                row.buy_volume += values["buy_volume"]
                row.sell_volume += values["sell_volume"]
                row.delta += values["delta"]
                row.trade_count += values["trade_count"]

        state.last_trade_id = accepted[-1]["trade_id"]
        state.updated_at = datetime.now(timezone.utc)
        db.commit()
        return len(accepted)
    except Exception:
        db.rollback()
        raise
