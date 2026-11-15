from datetime import datetime
from pydantic import BaseModel


class CandleResponse(BaseModel):
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
    taker_buy_volume: float | None = None


class MarketDataResponse(BaseModel):
    provider: str
    symbol: str
    timeframe: str
    count: int
    stored: int
    candles: list[CandleResponse]
