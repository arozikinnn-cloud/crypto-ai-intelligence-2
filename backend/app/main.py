import asyncio
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
import app.models.candle  # noqa: F401
import app.models.market_snapshot  # noqa: F401
import app.models.cvd_bucket  # noqa: F401
import app.models.cvd_collector_state  # noqa: F401
import app.models.liquidation_record  # noqa: F401
import app.models.signal_event  # noqa: F401
import app.models.device_token  # noqa: F401
from app.services.market_data.cvd_collector import stream_binance_aggtrades
from app.services.market_data.liquidation_collector import stream_binance_liquidations

settings = get_settings()
configure_logging()
IS_VERCEL = os.getenv("VERCEL") == "1"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Vercel runs short-lived, concurrent serverless instances. Do not run
    # create_all()/DDL migrations or persistent WebSocket collectors at startup:
    # concurrent create_all() calls can race on PostgreSQL's implicit table types
    # (for example pg_type_typname_nsp_index / candles).
    collector_tasks = []
    stop_event = asyncio.Event()

    if IS_VERCEL:
        # Apply only the idempotent additive PostgreSQL migration; never create
        # tables or start persistent collectors inside serverless instances.
        # Apply narrowly scoped additive migrations under a PostgreSQL advisory lock.
        migrate_schema(engine)
    else:
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
    version="0.3.0",
    description=(
        "Research-first crypto market intelligence API. "
        "Public market data only; no order execution."
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
