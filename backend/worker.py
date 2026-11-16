"""Standalone long-running Binance market-data collector process.

Run with: python -m worker
This process is intended for a persistent container/worker host, not Vercel
serverless functions. It stores public aggTrade CVD and futures liquidation
events in the configured SQL database.
"""
import asyncio
import logging
import signal

from app.core.config import get_settings
from app.database.base import Base
from app.database.migrations import migrate_schema
from app.database.session import engine
import app.models.candle  # noqa: F401
import app.models.market_snapshot  # noqa: F401
import app.models.cvd_bucket  # noqa: F401
import app.models.cvd_collector_state  # noqa: F401
import app.models.liquidation_record  # noqa: F401
import app.models.signal_event  # noqa: F401
import app.models.device_token  # noqa: F401
from app.services.market_data.cvd_collector import stream_binance_aggtrades
from app.services.market_data.liquidation_collector import stream_binance_liquidations

logger = logging.getLogger("crypto_ai.worker")


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


async def run_worker() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # The API and worker share the same database schema. Migrations are
    # idempotent and run before any collector opens a database session.
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)

    jobs = configured_collectors(settings)
    if not jobs:
        raise RuntimeError(
            "No collectors enabled. Enable CVD_COLLECTOR_ENABLED and/or "
            "LIQUIDATION_COLLECTOR_ENABLED."
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
    logger.info("Worker started with %d collector streams: %s", len(tasks), [
        task.get_name() for task in tasks
    ])
    try:
        await stop_event.wait()
    finally:
        logger.info("Shutdown requested; stopping collector streams.")
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Worker stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(run_worker())
