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
