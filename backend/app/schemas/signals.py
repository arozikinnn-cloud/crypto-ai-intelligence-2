from datetime import datetime
from pydantic import BaseModel


class SignalEventResponse(BaseModel):
    id: int
    symbol: str
    side: str
    status: str
    timeframe_set: str
    strategy_mode: str | None = None
    reasons: list[str]
    created_at: datetime
    updated_at: datetime
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    take_profit_3: float | None = None
    confirmation_score: str | None = None
    confidence_note: str | None = None
    outcome: str | None = None
    realized_r: float | None = None
    closed_at: datetime | None = None


class SignalNotificationResponse(BaseModel):
    id: int
    signal_id: int
    title: str
    message: str
    read: bool
    created_at: datetime
    strategy_mode: str | None = None
    symbol: str | None = None
    side: str | None = None
    signal_status: str | None = None
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    take_profit_3: float | None = None
    confirmation_score: str | None = None
    confidence_note: str | None = None
    signal_outcome: str | None = None
    signal_realized_r: float | None = None
    signal_closed_at: datetime | None = None
    signal_created_at: datetime | None = None
