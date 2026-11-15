from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CvdBucket(Base):
    __tablename__ = "cvd_buckets"
    __table_args__ = (
        UniqueConstraint("symbol", "source_market", "bucket_start_time", name="uq_cvd_bucket"),
        Index("ix_cvd_symbol_bucket", "symbol", "bucket_start_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    source_market: Mapped[str] = mapped_column(String(40), nullable=False)
    bucket_start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    buy_volume: Mapped[float] = mapped_column(Float, nullable=False)
    sell_volume: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)
