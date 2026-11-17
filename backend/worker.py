"""Standalone long-running Binance market-data collector process.

Run with: python -m worker
This process is intended for a persistent container/worker host, not Vercel
serverless functions. It stores public aggTrade CVD and futures liquidation
events in the configured SQL database.
"""
import asyncio
import logging
import signal

from sqlalchemy import select

from app.api.signals import evaluate_active_signals
from app.core.config import get_settings
from app.database.base import Base
from app.database.migrations import migrate_schema
from app.database.session import SessionLocal, engine
import app.models.candle  # noqa: F401
import app.models.market_snapshot  # noqa: F401
import app.models.cvd_bucket  # noqa: F401
import app.models.cvd_collector_state  # noqa: F401
import app.models.liquidation_record  # noqa: F401
import app.models.signal_event  # noqa: F401
import app.models.device_token  # noqa: F401
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.base import MarketDataError
from app.models.signal_event import SignalEvent
from app.services.market_data.cvd_collector import stream_binance_aggtrades
from app.services.market_data.liquidation_collector import stream_binance_liquidations

logger = logging.getLogger("crypto_ai.worker")


def validate_worker_database(settings) -> None:
    """Prevent production workers from silently writing to ephemeral SQLite."""
    is_production = settings.app_env.lower() == "production"
    uses_sqlite = settings.database_url.strip().lower().startswith("sqlite")
    if is_production and uses_sqlite:
        raise RuntimeError(
            "Production worker requires the same durable PostgreSQL DATABASE_URL "
            "used by the API; SQLite would create an isolated local database."
        )


def configured_collectors(settings):
    """Return enabled collector jobs as (name, async function, symbol, flush interval)."""
    jobs = []
    if settings.cvd_collector_enabled:
        jobs.extend(
            (
                f"cvd-{symbol}",
                stream_binance_aggtrades,
                symbol,
                settings.cvd_collector_flush_interval_seconds,
            )
            for symbol in settings.cvd_collector_symbol_list
        )
    if settings.liquidation_collector_enabled:
        jobs.extend(
            (
                f"liquidations-{symbol}",
                stream_binance_liquidations,
                symbol,
                settings.liquidation_collector_flush_interval_seconds,
            )
            for symbol in settings.liquidation_collector_symbol_list
        )
    return jobs



async def monitor_active_signals_once(market=None, session_factory=SessionLocal) -> int:
    """Evaluate active trade plans using the latest closed 15m Binance candle."""
    market = market or BinanceMarketData()
    db = session_factory()
    try:
        symbols = list(db.scalars(
            select(SignalEvent.symbol)
            .where(SignalEvent.status == "ACTIVE")
            .distinct()
        ))
    finally:
        db.close()

    evaluated = 0
    for symbol in symbols:
        try:
            candles = await market.fetch_klines(
                symbol, "15m", limit=2, closed_only=True
            )
            if not candles:
                continue
            candle = candles[-1]
            db = session_factory()
            try:
                evaluate_active_signals(
                    db,
                    symbol,
                    float(candle.high),
                    float(candle.low),
                    str(candle.close_time),
                )
                evaluated += 1
            finally:
                db.close()
        except (MarketDataError, ValueError, TypeError):
            logger.exception("Signal monitor failed for %s; retrying next cycle", symbol)
        except Exception:
            logger.exception("Unexpected signal monitor error for %s", symbol)
    return evaluated


async def monitor_active_signals(stop_event: asyncio.Event, poll_interval: float) -> None:
    """Keep TP/SL monitoring independent of Android app and API request traffic."""
    while not stop_event.is_set():
        await monitor_active_signals_once()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(5.0, poll_interval))
        except asyncio.TimeoutError:
            pass


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    validate_worker_database(settings)

    # The API and worker share the same database schema. Migrations are
    # idempotent and run before any collector opens a database session.
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)

    jobs = configured_collectors(settings)
    if not jobs and not settings.signal_monitor_enabled:
        raise RuntimeError(
            "No worker tasks enabled. Enable a collector or SIGNAL_MONITOR_ENABLED."
        )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Some non-POSIX runtimes do not expose asyncio signal handlers.
            pass

    tasks = [
        asyncio.create_task(
            collector(symbol, stop_event, flush_interval),
            name=name,
        )
        for name, collector, symbol, flush_interval in jobs
    ]
    if settings.signal_monitor_enabled:
        tasks.append(asyncio.create_task(
            monitor_active_signals(
                stop_event, settings.signal_monitor_poll_interval_seconds
            ),
            name="active-signal-tp-sl-monitor",
        ))
    logger.info("Worker started with %d tasks: %s", len(tasks), [
        task.get_name() for task in tasks
    ])
    stop_task = asyncio.create_task(stop_event.wait(), name="worker-shutdown")
    try:
        done, _ = await asyncio.wait(
            [stop_task, *tasks], return_when=asyncio.FIRST_COMPLETED
        )
        if stop_task not in done:
            failed_task = next(task for task in tasks if task in done)
            # A collector normally reconnects forever. If it exits, surface the
            # failure so the process supervisor can restart the worker.
            error = failed_task.exception()
            if error is not None:
                raise RuntimeError(
                    f"Worker task {failed_task.get_name()} stopped unexpectedly."
                ) from error
            raise RuntimeError(
                f"Worker task {failed_task.get_name()} exited unexpectedly."
            )
    finally:
        logger.info("Shutdown requested; stopping worker tasks.")
        stop_task.cancel()
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Worker stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(run_worker())
