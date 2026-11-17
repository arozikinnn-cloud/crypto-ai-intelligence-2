from datetime import datetime
from pydantic import BaseModel


class TechnicalIndicators(BaseModel):
    market_structure: str
    last_price: float | None
    ema20: float | None = None
    ema50: float | None = None
    rsi14: float | None = None
    ma40: float | None = None
    rsi16: float | None = None
    ichimoku_tenkan: float | None = None
    ichimoku_kijun: float | None = None
    ichimoku_senkou_a: float | None = None
    ichimoku_senkou_b: float | None = None
    ichimoku_cloud_top: float | None = None
    ichimoku_cloud_bottom: float | None = None
    ichimoku_above_cloud: bool = False
    ichimoku_below_cloud: bool = False
    ichimoku_bullish_breakout: bool = False
    ichimoku_bearish_breakout: bool = False
    ichimoku_bullish_retest: bool = False
    ichimoku_bearish_retest: bool = False
    macd: float | None = None
    macd_signal: float | None = None
    atr14: float | None = None
    volume_ratio: float | None = None
    support_20: float | None = None
    resistance_20: float | None = None


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
