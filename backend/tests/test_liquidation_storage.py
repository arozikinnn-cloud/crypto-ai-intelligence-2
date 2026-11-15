from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.base import Base
from app.services.market_data.liquidation_storage import (
    persist_liquidation_events,
    read_liquidation_history,
)


def test_liquidation_events_are_deduplicated_and_aggregated_by_minute():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    timestamp = datetime(2026, 11, 15, 10, 0, 30, tzinfo=timezone.utc)
    events = [
        {
            "event_key": "BTCUSDT:100:1000",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "price": 100000.0,
            "quantity": 0.1,
            "notional": 10000.0,
            "timestamp": timestamp,
        },
        {
            "event_key": "BTCUSDT:101:2000",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "price": 99000.0,
            "quantity": 0.2,
            "notional": 19800.0,
            "timestamp": timestamp,
        },
        {
            "event_key": "BTCUSDT:102:3000",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 101000.0,
            "quantity": 0.05,
            "notional": 5050.0,
            "timestamp": timestamp,
        },
    ]
    with Session(engine) as db:
        assert persist_liquidation_events(db, events + [events[0]]) == 3
        assert persist_liquidation_events(db, events) == 0
        history = read_liquidation_history(db, "BTCUSDT", 24)
        assert history["event_count"] == 3
        assert len(history["points"]) == 2
        sell = next(point for point in history["points"] if point["side"] == "SELL")
        assert sell["event_count"] == 2
        assert sell["total_quantity"] == pytest.approx(0.3)
        assert sell["total_notional"] == pytest.approx(29800.0)
    engine.dispose()
