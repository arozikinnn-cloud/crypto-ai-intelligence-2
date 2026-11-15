from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.cvd_bucket import CvdBucket
from app.services.market_data.cvd_storage import (
    persist_aggtrades_cvd,
    read_cvd_history,
)


def make_result(points):
    return {
        "symbol": "BTCUSDT",
        "source_market": "binance_spot_aggtrades",
        "cvd_scope": "returned_batch_only",
        "cumulative_delta": 999.0,
        "cvd_points": points,
        "method_note": "Test data.",
    }


def point(timestamp, delta, buy, sell):
    return {
        "bucket_start_time": timestamp,
        "buy_volume": buy,
        "sell_volume": sell,
        "delta": delta,
        "cumulative_delta": 0.0,
        "trade_count": 2,
    }


def test_cvd_storage_is_idempotent_and_rebuilds_cumulative_history():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = persist_aggtrades_cvd(
            db,
            make_result([
                point(1_767_225_600_000, 1.0, 2.0, 1.0),
                point(1_767_225_660_000, 1.0, 3.0, 2.0),
            ]),
        )
        assert first["cvd_scope"] == "persisted_observed_history"
        assert [item["cumulative_delta"] for item in first["cvd_points"]] == [1.0, 2.0]
        assert first["cumulative_delta"] == 2.0

        updated = persist_aggtrades_cvd(
            db,
            make_result([point(1_767_225_660_000, -1.0, 1.0, 2.0)]),
        )
        assert updated["cvd_points"][0]["cumulative_delta"] == 0.0
        rows = db.scalars(select(CvdBucket)).all()
        assert len(rows) == 2
        assert rows[1].delta == -1.0
    engine.dispose()


def test_read_cvd_history_returns_persisted_points_and_cumulative_offset():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        persist_aggtrades_cvd(
            db,
            make_result([
                point(1_767_225_600_000, 1.0, 2.0, 1.0),
                point(1_767_225_660_000, -0.5, 1.0, 1.5),
            ]),
        )
        history = read_cvd_history(db, "BTCUSDT", 10)
        assert len(history["points"]) == 2
        assert history["points"][-1]["cumulative_delta"] == 0.5
        assert history["cumulative_delta"] == 0.5
        assert history["cvd_scope"] == "persisted_observed_history"
    engine.dispose()
