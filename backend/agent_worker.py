"""Standalone TradingAgents job worker.

Run as a separate persistent process: python -m agent_worker.
It is intentionally not imported by Vercel's short-lived FastAPI functions.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.database.base import Base
from app.database.migrations import migrate_schema
from app.database.session import SessionLocal, engine
from app.models.agent_analysis_job import AgentAnalysisJob
from app.services.analysis.tradingagents_result import normalize_tradingagents_result

logger = logging.getLogger("crypto_ai.tradingagents_worker")


def run_tradingagents(symbol: str) -> dict:
    """Run the official multi-agent framework for a crypto asset."""
    # Import the optional, heavyweight dependency only in this worker process.
    from tradingagents.agents.rating import run_rating
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ticker = f"{symbol[:-4]}-USD" if symbol.endswith("USDT") else symbol
    config = DEFAULT_CONFIG.copy()
    config["output_language"] = os.getenv("TRADINGAGENTS_OUTPUT_LANGUAGE", "Indonesian")
    config["max_debate_rounds"] = int(os.getenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "1"))
    config["max_risk_discuss_rounds"] = int(os.getenv("TRADINGAGENTS_MAX_RISK_ROUNDS", "1"))
    config["max_tool_rounds"] = int(os.getenv("TRADINGAGENTS_MAX_TOOL_ROUNDS", "4"))
    config["max_recur_limit"] = max(30, 2 * config["max_tool_rounds"] + 10)
    config["checkpoint_enabled"] = True
    config["results_dir"] = os.getenv("TRADINGAGENTS_RESULTS_DIR", "/data/tradingagents/results")
    config["data_cache_dir"] = os.getenv("TRADINGAGENTS_CACHE_DIR", "/data/tradingagents/cache")
    config["memory_log_path"] = os.getenv(
        "TRADINGAGENTS_MEMORY_LOG_PATH", "/data/tradingagents/memory/trading_memory.md"
    )

    graph = TradingAgentsGraph(
        selected_analysts=("market", "social", "news"),
        debug=False,
        config=config,
    )
    state, _decision = graph.propagate(
        ticker,
        datetime.now(timezone.utc).date().isoformat(),
        asset_type="crypto",
    )
    rating = run_rating(state)
    final_decision = state.get("final_trade_decision", "")
    reports = {
        key: state.get(key)
        for key in (
            "market_report",
            "sentiment_report",
            "news_report",
            "investment_plan",
            "trader_investment_plan",
            "final_trade_decision",
        )
        if isinstance(state.get(key), str)
    }
    return normalize_tradingagents_result(rating, final_decision, reports)


def process_agent_analysis_once(session_factory=SessionLocal) -> bool:
    """Claim and process one queued job; PostgreSQL row locking prevents double claims."""
    db = session_factory()
    job_id = None
    symbol = None
    try:
        job = db.scalar(
            select(AgentAnalysisJob)
            .where(AgentAnalysisJob.status == "PENDING")
            .order_by(AgentAnalysisJob.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        job_id, symbol = job.id, job.symbol
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    try:
        result = asyncio.run(asyncio.to_thread(run_tradingagents, symbol))
        status, error = "COMPLETED", None
    except Exception as exc:
        logger.exception("TradingAgents job %s failed", job_id)
        result = None
        status = "FAILED"
        error = f"{type(exc).__name__}: {str(exc)[:1000]}"

    db = session_factory()
    try:
        job = db.get(AgentAnalysisJob, job_id)
        if job is not None:
            job.status = status
            job.completed_at = datetime.now(timezone.utc)
            job.result_json = json.dumps(result, ensure_ascii=False) if result else None
            job.error_message = error
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return True


async def run_agent_analysis_worker(stop_event: asyncio.Event, poll_seconds: float) -> None:
    while not stop_event.is_set():
        processed = await asyncio.to_thread(process_agent_analysis_once)
        if processed:
            continue
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(2.0, poll_seconds))
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    settings = get_settings()
    if not settings.tradingagents_enabled:
        raise RuntimeError("Set TRADINGAGENTS_ENABLED=true on the agent worker.")
    if settings.app_env.lower() == "production" and settings.database_url.startswith("sqlite"):
        raise RuntimeError("Production TradingAgents worker requires shared PostgreSQL DATABASE_URL.")
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)
    stop_event = asyncio.Event()
    logger.info("TradingAgents worker started.")
    try:
        await run_agent_analysis_worker(stop_event, settings.tradingagents_poll_interval_seconds)
    finally:
        stop_event.set()
        logger.info("TradingAgents worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
