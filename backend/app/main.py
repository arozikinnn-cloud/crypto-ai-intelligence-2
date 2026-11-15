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

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_schema(engine)
    yield


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
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running", "docs": "/docs"}
