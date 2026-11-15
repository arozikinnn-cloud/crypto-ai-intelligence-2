from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cvd_bucket import CvdBucket


def persist_aggtrades_cvd(db: Session, result: dict) -> dict:
    """Persist overlapping minute buckets idempotently and rebuild observed-history CVD."""
    points = result.get("cvd_points", [])
    if not points:
        return result

    symbol = result["symbol"].upper()
    source_market = result["source_market"]
    normalized_points = []
    for point in points:
        bucket_time = datetime.fromtimestamp(
            int(point["bucket_start_time"]) / 1000, tz=timezone.utc
        )
        normalized_points.append((bucket_time, point))

    try:
        for bucket_time, point in normalized_points:
            existing = db.scalar(
                select(CvdBucket).where(
                    CvdBucket.symbol == symbol,
                    CvdBucket.source_market == source_market,
                    CvdBucket.bucket_start_time == bucket_time,
                )
            )
            values = {
                "buy_volume": float(point["buy_volume"]),
                "sell_volume": float(point["sell_volume"]),
                "delta": float(point["delta"]),
                "trade_count": int(point["trade_count"]),
            }
            if existing is None:
                db.add(
                    CvdBucket(
                        symbol=symbol,
                        source_market=source_market,
                        bucket_start_time=bucket_time,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
        db.flush()

        first_bucket = normalized_points[0][0]
        cumulative = db.scalar(
            select(func.coalesce(func.sum(CvdBucket.delta), 0.0)).where(
                CvdBucket.symbol == symbol,
                CvdBucket.source_market == source_market,
                CvdBucket.bucket_start_time < first_bucket,
            )
        )
        cumulative = float(cumulative or 0.0)
        rebuilt = []
        for bucket_time, point in normalized_points:
            cumulative += float(point["delta"])
            rebuilt.append({**point, "cumulative_delta": cumulative})
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        **result,
        "cvd_points": rebuilt,
        "cumulative_delta": cumulative,
        "cvd_scope": "persisted_observed_history",
        "method_note": (
            result.get("method_note", "")
            + " Bucket disimpan lokal secara idempoten; CVD dihitung dari riwayat "
            "bucket yang berhasil diamati oleh aplikasi. Jeda saat aplikasi mati "
            "atau sumber data gagal dapat membuat riwayat tidak lengkap."
        ),
    }
