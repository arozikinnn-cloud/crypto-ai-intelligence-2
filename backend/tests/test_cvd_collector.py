from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database.base import Base
from app.models.cvd_bucket import CvdBucket
from app.models.cvd_collector_state import CvdCollectorState
from app.services.market_data.cvd_collector import normalize_aggtrade_event
from app.services.market_data.cvd_collector_storage import persist_aggtrade_events


def test_normalize_aggtrade_websocket_event():
    event = normalize_aggtrade_event(
        {
            "s": "BTCUSDT",
            "a": 101,
            "T": 1_767_225_600_123,
            "q": "0.25",
            "m": False,
        },
        "BTCUSDT",
    )
    assert event == {
        "trade_id": 101,
        "timestamp": 1_767_225_600_123,
        "quantity": 0.25,
        "buyer_is_maker": False,
    }


def test_reject_aggtrade_event_for_wrong_symbol():
    import pytest

    with pytest.raises(ValueError):
        normalize_aggtrade_event(
            {"s": "ETHUSDT", "a": 1, "T": 1_767_225_600_123, "q": "1", "m": True},
            "BTCUSDT",
        )


def test_streamed_aggtrades_are_persisted_once_and_accumulated():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    events = [
        {
            "trade_id": 101,
            "timestamp": 1_767_225_600_123,
            "quantity": 0.25,
            "buyer_is_maker": False,
        },
        {
            "trade_id": 102,
            "timestamp": 1_767_225_610_123,
            "quantity": 0.10,
            "buyer_is_maker": True,
        },
    ]
    with Session(engine) as db:
        assert persist_aggtrade_events(db, "BTCUSDT", events + [events[0]]) == 2
        assert persist_aggtrade_events(db, "BTCUSDT", events) == 0

        bucket = db.scalars(select(CvdBucket)).one()
        assert bucket.buy_volume == 0.25
        assert bucket.sell_volume == 0.10
        assert bucket.delta == 0.15
        assert bucket.trade_count == 2

        state = db.get(CvdCollectorState, "BTCUSDT")
        assert state.last_trade_id == 102
    engine.dispose()
