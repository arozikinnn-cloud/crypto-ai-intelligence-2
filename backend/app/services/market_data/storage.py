from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.candle import Candle
from app.services.market_data.base import NormalizedCandle


def store_candles(db: Session, provider: str, candles: list[NormalizedCandle]) -> int:
    stored = 0
    fetched_at = datetime.now(timezone.utc)
    for item in candles:
        existing = db.scalar(
            select(Candle).where(
                Candle.provider == provider,
                Candle.symbol == item.symbol,
                Candle.timeframe == item.timeframe,
                Candle.open_time == item.open_time,
            )
        )
        values = {
            "close_time": item.close_time, "open": item.open, "high": item.high,
            "low": item.low, "close": item.close, "volume": item.volume,
            "quote_volume": item.quote_volume, "trades": item.trades,
            "taker_buy_volume": item.taker_buy_volume, "fetched_at": fetched_at,
        }
        if existing is None:
            db.add(Candle(provider=provider, symbol=item.symbol, timeframe=item.timeframe,
                          open_time=item.open_time, **values))
            stored += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
    db.commit()
    return stored
