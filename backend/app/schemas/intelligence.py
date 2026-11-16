from datetime import datetime
from pydantic import BaseModel
from app.schemas.analysis import AnalysisResponse
from app.schemas.order_flow import (
    AggTradesOrderFlowResponse,
    OrderFlowResponse,
    DerivativesContextResponse,
)
from app.schemas.structure import StructureResponse


class IntelligenceResponse(BaseModel):
    symbol: str
    timestamp: datetime
    side: str
    confluence_score: int
    max_confluence: int
    score_note: str
    reasons: list[str]
    context_notes: list[str]
    checks: dict[str, bool]
    timeframe_analyses: list[AnalysisResponse]
    structure: StructureResponse
    order_flow: OrderFlowResponse
    aggtrades_order_flow: AggTradesOrderFlowResponse
    derivatives: DerivativesContextResponse
    market_context: dict
    strategy_mode: str = "DAY_TRADING"
    trade_plan: dict | None = None
