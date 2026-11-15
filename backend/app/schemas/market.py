from datetime import datetime
from pydantic import BaseModel, ConfigDict


class CandleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
    fetched_at: datetime


class MarketDataResponse(BaseModel):
    provider: str
    symbol: str
    timeframe: str
    count: int
    stored: int
    candles: list[CandleResponse]
