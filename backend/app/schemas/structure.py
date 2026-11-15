from datetime import datetime
from pydantic import BaseModel


class FairValueGap(BaseModel):
    low: float
    high: float
    formed_at: datetime


class StructureResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    trend: str
    event: str
    last_swing_high: float | None
    last_swing_low: float | None
    bullish_fvg: FairValueGap | None
    bearish_fvg: FairValueGap | None
    pivot_count: int
    method_note: str
