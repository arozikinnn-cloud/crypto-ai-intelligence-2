from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CvdCollectorState(Base):
    __tablename__ = "cvd_collector_states"

    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    last_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=-1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
