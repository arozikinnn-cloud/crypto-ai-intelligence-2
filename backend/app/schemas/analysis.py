from datetime import datetime
from pydantic import BaseModel


class TechnicalIndicators(BaseModel):
    last_price: float | None
    ema20: float | None
    ema50: float | None
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    atr14: float | None
    volume_ratio: float | None
    support_20: float | None
    resistance_20: float | None


class AnalysisResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    side: str
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    risk_reward: float | None
    confluence_score: int
    max_confluence: int
    score_note: str
    indicators: TechnicalIndicators
    reasons: list[str]
    candle_count: int
