from pydantic import BaseModel


class BacktestMetrics(BaseModel):
    trades: int
    win_rate_pct: float
    total_return_pct: float
    profit_factor: float | None
    max_drawdown_pct: float


class BacktestResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: int
    train_ratio: float
    fee_bps_per_side: float
    slippage_bps_per_side: float
    strategy: str
    train: BacktestMetrics
    out_of_sample: BacktestMetrics
    warning: str
