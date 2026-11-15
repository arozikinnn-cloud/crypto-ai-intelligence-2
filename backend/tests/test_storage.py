from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.database.base import Base
from app.database.migrations import migrate_schema
from app.models.candle import Candle
from app.services.market_data.base import NormalizedCandle
from app.services.market_data.storage import store_candles


def make_candle(buy_volume=6.5):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return NormalizedCandle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=now,
        close_time=now,
        open=100,
        high=102,
        low=99,
        close=101,
        volume=10,
        quote_volume=1010,
        trades=12,
        taker_buy_volume=buy_volume,
    )


def test_storage_round_trips_taker_buy_volume_and_updates_existing_row():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert store_candles(db, "binance", [make_candle()]) == 1
        saved = db.query(Candle).one()
        assert saved.taker_buy_volume == 6.5

        assert store_candles(db, "binance", [make_candle(7.25)]) == 0
        db.refresh(saved)
        assert saved.taker_buy_volume == 7.25
    engine.dispose()


def test_migration_adds_nullable_column_to_existing_candle_table():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE candles (id INTEGER PRIMARY KEY, symbol VARCHAR(30))"
        ))

    migrate_schema(engine)
    columns = {column["name"] for column in inspect(engine).get_columns("candles")}
    assert "taker_buy_volume" in columns
    engine.dispose()
