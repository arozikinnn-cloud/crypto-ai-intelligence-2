from pydantic import BaseModel, Field


class BacktestMetrics(BaseModel):
    trades: int
    win_rate_pct: float
    total_return_pct: float
    profit_factor: float | None
    max_drawdown_pct: float
    wins: int = 0
    losses: int = 0
    flats: int = 0
    expectancy_pct: float = 0.0


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
    overall: BacktestMetrics | None = None
    signal_count: int = 0
    no_trade_count: int = 0
    quality_checks: dict[str, bool] = Field(default_factory=dict)
