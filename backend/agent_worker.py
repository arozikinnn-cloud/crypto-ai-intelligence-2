"""Standalone TradingAgents job worker.

Run as a separate persistent process: python -m agent_worker.
It is intentionally not imported by Vercel's short-lived FastAPI functions.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.core.config import get_settings
from app.api.signals import record_signal
from app.database.base import Base
from app.database.migrations import migrate_schema
from app.database.session import SessionLocal, engine
from app.models.agent_analysis_job import AgentAnalysisJob
from app.services.analysis.tradingagents_market_context import (
    collect_bitget_v8_context,
    finalize_v8_decision,
)

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

    # Pull the exchange-native market context first. If Bitget data is missing or
    # stale, fail closed instead of silently producing a Yahoo-only trade signal.
    market_context = asyncio.run(collect_bitget_v8_context(symbol))
    graph = TradingAgentsGraph(
        selected_analysts=("market", "social", "news"),
        debug=False,
        config=config,
    )
    upstream_resolver = graph.resolve_instrument_context

    def resolve_with_bitget(ticker_name, asset_type="stock", trade_date=None):
        try:
            identity_context = upstream_resolver(ticker_name, asset_type, trade_date)
        except Exception:
            identity_context = (
                f"Instrument: {ticker_name}. Identity lookup unavailable; "
                "do not infer company identity."
            )
        return identity_context + "\n\n" + market_context["context_text"]

    # The upstream graph passes this instrument context to all analyst prompts.
    graph.resolve_instrument_context = resolve_with_bitget
    state, rating = graph.propagate(
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
    return finalize_v8_decision(rating, final_decision, reports, market_context)


def recover_stale_agent_jobs(db, stale_after_minutes: int = 120) -> int:
    """Requeue jobs abandoned by a crashed worker after a conservative lease timeout.

    The scheduled free-tier runner has a 55-minute hard timeout, so the default
    two-hour lease avoids racing a healthy scheduled job while recovering jobs
    left RUNNING by terminated containers or interrupted deployments.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max(60, stale_after_minutes)
    )
    result = db.execute(
        update(AgentAnalysisJob)
        .where(
            AgentAnalysisJob.status == "RUNNING",
            AgentAnalysisJob.started_at.is_not(None),
            AgentAnalysisJob.started_at < cutoff,
        )
        .values(
            status="PENDING",
            started_at=None,
            error_message="Automatically requeued after stale worker lease expired.",
        )
    )
    return result.rowcount or 0


def process_agent_analysis_once(session_factory=SessionLocal) -> bool:
    """Claim and process one queued job; PostgreSQL row locking prevents double claims."""
    db = session_factory()
    job_id = None
    symbol = None
    try:
        # Recover jobs abandoned by a killed worker before claiming new work.
        settings = get_settings()
        recover_stale_agent_jobs(
            db, getattr(settings, "tradingagents_job_stale_minutes", 120)
        )
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
        result = run_tradingagents(symbol)
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
        if status == "COMPLETED" and result and result.get("trade_plan"):
            plan = result["trade_plan"]
            market_context = result.get("market_context") or {}
            timeframes = market_context.get("timeframes") or {}
            signal_candle_timestamp = (
                (timeframes.get("15m") or {}).get("candle_close_time")
                or datetime.now(timezone.utc).isoformat()
            )
            signal_db = session_factory()
            try:
                record_signal(
                    signal_db,
                    symbol,
                    result.get("side", ""),
                    ["1h", "30m", "15m", "5m"],
                    result.get("reasons") or [],
                    signal_candle_timestamp,
                    plan,
                    signal_candle_timestamp=signal_candle_timestamp,
                    strategy_mode="TRADINGAGENTS_MULTI_AGENT_V8",
                )
            except Exception:
                signal_db.rollback()
                logger.exception(
                    "V8 analysis job %s completed but signal persistence failed",
                    job_id,
                )
            finally:
                signal_db.close()
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
        raise RuntimeError(
            "Production TradingAgents worker requires shared PostgreSQL DATABASE_URL."
        )
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)
    stop_event = asyncio.Event()
    logger.info("TradingAgents worker started.")
    try:
        if "--once" in sys.argv:
            processed = await asyncio.to_thread(process_agent_analysis_once)
            logger.info("One-shot cycle finished; processed_job=%s", processed)
        else:
            await run_agent_analysis_worker(
                stop_event,
                settings.tradingagents_poll_interval_seconds,
            )
    finally:
        stop_event.set()
        logger.info("TradingAgents worker stopped.")


if __name__ == "__main__":
    asyncio.run(main())
