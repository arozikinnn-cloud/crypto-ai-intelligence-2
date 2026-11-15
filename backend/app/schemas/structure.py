from datetime import datetime

from pydantic import BaseModel


class PriceZone(BaseModel):
    low: float
    high: float
    formed_at: datetime


class FairValueGap(PriceZone):
    mitigated: bool
    fully_mitigated: bool


class StructureResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    trend: str
    event: str
    liquidity_sweep: str
    last_swing_high: float | None
    last_swing_low: float | None
    bullish_fvg: FairValueGap | None
    bearish_fvg: FairValueGap | None
    bullish_order_block: PriceZone | None
    bearish_order_block: PriceZone | None
    pivot_count: int
    method_note: str
