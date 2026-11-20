from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.order_flow import (
    AggTradesOrderFlowResponse,
    CvdHistoryResponse,
    DerivativesContextResponse,
    OrderFlowResponse,
)
from app.services.analysis.order_flow import analyze_order_flow
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.binance_futures import BinanceFuturesMarketData
from app.services.market_data.binance_aggtrades import BinanceAggTradesMarketData
from app.services.market_data.cvd_storage import persist_aggtrades_cvd, read_cvd_history

router = APIRouter(prefix="/analysis", tags=["order-flow and derivatives"])


@router.get("/order-flow", response_model=OrderFlowResponse)
async def order_flow_analysis(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    interval: str = Query(default="5m"),
    lookback: int = Query(default=20, ge=2, le=100),
) -> OrderFlowResponse:
    if interval not in BinanceMarketData.ALLOWED_INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported candle interval.")
    try:
        # Ask for one extra candle because the newest kline is usually still open.
        # closed_only filters it out; the extra row preserves the requested lookback.
        candles = await BinanceMarketData().fetch_klines(
            symbol, interval, lookback + 1, closed_only=True
        )
        result = analyze_order_flow(candles, lookback)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderFlowResponse(**result)


@router.get("/order-flow/aggtrades", response_model=AggTradesOrderFlowResponse)
async def aggtrades_order_flow(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    limit: int = Query(default=500, ge=10, le=1000),
    db: Session = Depends(get_db),
) -> AggTradesOrderFlowResponse:
    """Recent trade-level aggressor delta from Binance public aggregated trades."""
    try:
        result = await BinanceAggTradesMarketData().fetch_order_flow(symbol, limit)
        # Keep minute buckets progressing whenever the dashboard requests live
        # aggressor flow. The upsert is idempotent for overlapping API batches.
        result = persist_aggtrades_cvd(db, result)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return AggTradesOrderFlowResponse(**result)


@router.get("/order-flow/cvd-history", response_model=CvdHistoryResponse)
def cvd_history(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> CvdHistoryResponse:
    try:
        result = read_cvd_history(db, symbol, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CvdHistoryResponse(**result)


@router.get("/derivatives", response_model=DerivativesContextResponse)
async def derivatives_context(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    period: str = Query(default="5m"),
) -> DerivativesContextResponse:
    try:
        result = await BinanceFuturesMarketData().fetch_derivatives_context(
            symbol, period
        )
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return DerivativesContextResponse(**result)
