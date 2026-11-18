from datetime import datetime

from pydantic import BaseModel


class AgentAnalysisJobResponse(BaseModel):
    id: int
    symbol: str
    status: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict | None = None
    error_message: str | None = None
