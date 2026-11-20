import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.database.base import Base
from app.database.session import engine
from app.database.migrations import migrate_schema
import app.models.agent_analysis_job  # noqa: F401
import app.models.candle  # noqa: F401
import app.models.market_snapshot  # noqa: F401
import app.models.cvd_bucket  # noqa: F401
import app.models.cvd_collector_state  # noqa: F401
import app.models.liquidation_record  # noqa: F401
import app.models.signal_event  # noqa: F401
import app.models.device_token  # noqa: F401

settings = get_settings()
configure_logging()
logger = logging.getLogger("crypto_ai.startup")
IS_VERCEL = os.getenv("VERCEL") == "1"
IS_PREVIEW = os.getenv("VERCEL_ENV", "").lower() == "preview"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Vercel instances are short-lived. Do not run persistent collectors there.
    collector_tasks = []
    stop_event = asyncio.Event()

    if IS_VERCEL:
        try:
            # Preview may be used for API smoke tests while its external database
            # is being configured. Keep liveness and public market endpoints up,
            # but never pretend the database is ready when connection/migration fails.
            if engine.dialect.name == "sqlite":
                # Preview's disposable SQLite database is initialized from the
                # complete ORM metadata. Skip custom DDL migrations here to keep
                # serverless cold starts short and avoid repeated schema work.
                Base.metadata.create_all(bind=engine)
            else:
                migrate_schema(engine)
        except Exception:
            if not IS_PREVIEW:
                raise
            logger.exception(
                "Preview database initialization failed; starting in degraded "
                "read-only mode. Database-backed endpoints remain unavailable."
            )
    else:
        # Persistent WebSocket collectors are only imported in a long-lived
        # process, never in Vercel's short-lived serverless runtime.
        from app.services.market_data.cvd_collector import stream_binance_aggtrades
        from app.services.market_data.liquidation_collector import stream_binance_liquidations

        Base.metadata.create_all(bind=engine)
        migrate_schema(engine)

        if settings.cvd_collector_enabled:
            collector_tasks.extend(
                asyncio.create_task(
                    stream_binance_aggtrades(
                        symbol, stop_event, settings.cvd_collector_flush_interval_seconds
                    ),
                    name=f"cvd-collector-{symbol}",
                ) for symbol in settings.cvd_collector_symbol_list
            )
        if settings.liquidation_collector_enabled:
            collector_tasks.extend(
                asyncio.create_task(
                    stream_binance_liquidations(
                        symbol, stop_event,
                        settings.liquidation_collector_flush_interval_seconds
                    ),
                    name=f"liquidation-collector-{symbol}",
                ) for symbol in settings.liquidation_collector_symbol_list
            )

    try:
        yield
    finally:
        stop_event.set()
        for task in collector_tasks:
            task.cancel()
        if collector_tasks:
            await asyncio.gather(*collector_tasks, return_exceptions=True)


app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description=(
        "Crypto AI Intelligence V8 research API powered by a separately hosted "
        "TradingAgents worker. No exchange order execution is enabled."
    ),
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origin_list,
    allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}
