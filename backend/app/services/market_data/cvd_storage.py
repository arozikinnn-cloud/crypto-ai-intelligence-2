from datetime import datetime, timezone

from sqlalchemy import desc, func, select
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



def read_cvd_history(db: Session, symbol: str, limit: int = 500) -> dict:
    normalized = symbol.upper().strip()
    if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
        raise ValueError("Invalid trading symbol.")
    if not 1 <= limit <= 2000:
        raise ValueError("CVD history limit must be between 1 and 2000.")

    rows = db.scalars(
        select(CvdBucket)
        .where(
            CvdBucket.symbol == normalized,
            CvdBucket.source_market == "binance_spot_aggtrades",
        )
        .order_by(desc(CvdBucket.bucket_start_time))
        .limit(limit)
    ).all()
    rows = list(reversed(rows))
    if not rows:
        return {
            "symbol": normalized,
            "source_market": "binance_spot_aggtrades",
            "cvd_bucket_interval": "1m",
            "cvd_scope": "persisted_observed_history",
            "points": [],
            "cumulative_delta": 0.0,
            "note": "Belum ada bucket CVD yang tersimpan untuk simbol ini.",
        }

    cumulative = db.scalar(
        select(func.coalesce(func.sum(CvdBucket.delta), 0.0)).where(
            CvdBucket.symbol == normalized,
            CvdBucket.source_market == "binance_spot_aggtrades",
            CvdBucket.bucket_start_time < rows[0].bucket_start_time,
        )
    )
    running = float(cumulative or 0.0)
    points = []
    for row in rows:
        running += row.delta
        points.append(
            {
                "bucket_start_time": int(row.bucket_start_time.replace(tzinfo=timezone.utc).timestamp() * 1000),
                "buy_volume": row.buy_volume,
                "sell_volume": row.sell_volume,
                "delta": row.delta,
                "cumulative_delta": running,
                "trade_count": row.trade_count,
            }
        )
    return {
        "symbol": normalized,
        "source_market": "binance_spot_aggtrades",
        "cvd_bucket_interval": "1m",
        "cvd_scope": "persisted_observed_history",
        "points": points,
        "cumulative_delta": running,
        "note": (
            "Riwayat ini hanya mencakup bucket yang berhasil dikumpulkan aplikasi. "
            "Jeda saat aplikasi mati atau data sumber gagal dapat menyebabkan gap."
        ),
    }
