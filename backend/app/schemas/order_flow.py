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


class CvdPoint(BaseModel):
    bucket_start_time: int
    buy_volume: float
    sell_volume: float
    delta: float
    cumulative_delta: float
    trade_count: int


class AggTradesOrderFlowResponse(BaseModel):
    symbol: str
    source_market: str
    trade_count: int
    buy_aggressor_volume: float
    sell_aggressor_volume: float
    net_delta: float
    delta_percent: float
    cumulative_delta: float
    cvd_bucket_interval: str
    cvd_scope: str
    cvd_points: list[CvdPoint]
    bias: str
    first_trade_time: int | None
    last_trade_time: int | None
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



class CvdHistoryResponse(BaseModel):
    symbol: str
    source_market: str
    cvd_bucket_interval: str
    cvd_scope: str
    points: list[CvdPoint]
    cumulative_delta: float
    note: str
