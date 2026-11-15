from datetime import datetime
from sqlalchemy import DateTime, Float, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("provider", "symbol", "timeframe", "open_time", name="uq_candle_identity"),
        Index("ix_candles_symbol_timeframe_open", "symbol", "timeframe", "open_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), default="binance")
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    timeframe: Mapped[str] = mapped_column(String(10))
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)
    quote_volume: Mapped[float] = mapped_column(Float)
    trades: Mapped[int] = mapped_column()
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
