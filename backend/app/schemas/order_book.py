from pydantic import BaseModel


class OrderBookAnalysisResponse(BaseModel):
    symbol: str
    source_market: str
    depth_levels: int
    bid_notional: float
    ask_notional: float
    imbalance: float
    imbalance_percent: float
    spread_bps: float
    best_bid: float
    best_ask: float
    bias: str
    method_note: str
