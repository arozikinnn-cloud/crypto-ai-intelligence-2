from datetime import datetime
from pydantic import BaseModel


class SignalEventResponse(BaseModel):
    id: int
    symbol: str
    side: str
    status: str
    timeframe_set: str
    reasons: list[str]
    created_at: datetime
    updated_at: datetime


class SignalNotificationResponse(BaseModel):
    id: int
    signal_id: int
    title: str
    message: str
    read: bool
    created_at: datetime
