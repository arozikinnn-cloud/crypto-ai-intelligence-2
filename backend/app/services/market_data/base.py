from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NormalizedCandle:
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


class MarketDataError(Exception):
    """Raised when an exchange response cannot be fetched or normalized."""
