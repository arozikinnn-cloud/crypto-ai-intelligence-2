import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_db
from app.models.agent_analysis_job import AgentAnalysisJob
from app.schemas.agent_analysis import AgentAnalysisJobResponse

router = APIRouter(prefix="/agent-analysis", tags=["TradingAgents V8"])
_SYMBOL_RE = re.compile(r"^[A-Z0-9]{5,20}$")


def _serialize(job: AgentAnalysisJob) -> AgentAnalysisJobResponse:
    result = None
    if job.result_json:
        try:
            result = json.loads(job.result_json)
        except json.JSONDecodeError:
            result = {"status": "RESULT_UNREADABLE"}
    return AgentAnalysisJobResponse(
        id=job.id,
        symbol=job.symbol,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=result,
        error_message=job.error_message,
    )


@router.post("/jobs", response_model=AgentAnalysisJobResponse, status_code=202)
def create_agent_analysis_job(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20),
    db: Session = Depends(get_db),
) -> AgentAnalysisJobResponse:
    settings = get_settings()
    if not settings.tradingagents_enabled:
        raise HTTPException(
            status_code=503,
            detail="TradingAgents V8 is not enabled. Configure its worker and model provider first.",
        )
    normalized = symbol.strip().upper()
    if not _SYMBOL_RE.fullmatch(normalized) or not normalized.endswith("USDT"):
        raise HTTPException(
            status_code=422,
            detail="Only alphanumeric USDT crypto pairs such as BTCUSDT are supported.",
        )
    base = normalized[:-4]
    job = AgentAnalysisJob(symbol=normalized, ticker=f"{base}-USD", status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    return _serialize(job)


@router.get("/jobs/{job_id}", response_model=AgentAnalysisJobResponse)
def get_agent_analysis_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> AgentAnalysisJobResponse:
    job = db.get(AgentAnalysisJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Agent analysis job not found.")
    return _serialize(job)


@router.get("/jobs", response_model=list[AgentAnalysisJobResponse])
def list_agent_analysis_jobs(
    symbol: str | None = Query(default=None, min_length=5, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AgentAnalysisJobResponse]:
    from sqlalchemy import select

    statement = select(AgentAnalysisJob).order_by(
        AgentAnalysisJob.created_at.desc()
    ).limit(limit)
    if symbol:
        statement = statement.where(AgentAnalysisJob.symbol == symbol.strip().upper())
    return [_serialize(job) for job in db.scalars(statement)]
