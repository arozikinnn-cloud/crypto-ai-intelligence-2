from datetime import datetime
from pydantic import BaseModel
from app.schemas.analysis import AnalysisResponse


class MultiTimeframeResponse(BaseModel):
    symbol: str
    timestamp: datetime
    overall_side: str
    aligned_timeframes: int
    total_timeframes: int
    analyses: list[AnalysisResponse]
    reasons: list[str]
