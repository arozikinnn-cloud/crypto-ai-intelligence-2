from datetime import datetime
from pydantic import BaseModel


class LiquidationEvent(BaseModel):
    symbol: str
    source_market: str
    side: str
    price: float
    quantity: float
    notional: float
    timestamp: datetime
    order_status: str
    note: str



class LiquidationHistoryPoint(BaseModel):
    bucket_start_time: int
    side: str
    event_count: int
    total_quantity: float
    total_notional: float
    min_price: float
    max_price: float


class LiquidationHistoryResponse(BaseModel):
    symbol: str
    source_market: str
    hours: int
    event_count: int
    points: list[LiquidationHistoryPoint]
    note: str
