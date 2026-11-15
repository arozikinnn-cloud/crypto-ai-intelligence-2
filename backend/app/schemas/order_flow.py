from pydantic import BaseModel


class OrderFlowResponse(BaseModel):
    symbol: str
    timeframe: str
    source_market: str
    lookback: int
    buy_volume: float
    sell_volume: float
    net_delta: float
    delta_percent: float
    cumulative_delta: float
    bias: str
    method_note: str


class DerivativesContextResponse(BaseModel):
    symbol: str
    source_market: str
    open_interest_unit: str
    open_interest: float
    open_interest_change_percent: float | None
    open_interest_period: str
    funding_rate: float
    funding_time: int
    interpretation: str
