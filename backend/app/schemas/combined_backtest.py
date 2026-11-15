from pydantic import BaseModel


class CombinedBacktestStats(BaseModel):
    trades: int
    wins: int
    losses: int
    flats: int
    win_rate_pct: float
    total_return_pct: float
    expectancy_pct: float
    profit_factor: float | None
    max_drawdown_pct: float


class CombinedBacktestResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: int
    strategy: str
    execution: str
    horizon_candles: int
    fee_bps_per_side: float
    slippage_bps_per_side: float
    train: CombinedBacktestStats
    out_of_sample: CombinedBacktestStats
    overall: CombinedBacktestStats
    signal_count: int
    no_trade_count: int
    quality_checks: dict[str, bool]
    limitations: list[str]


class TimeframePerformanceResponse(BaseModel):
    symbol: str
    results: list[CombinedBacktestResponse]
    note: str
