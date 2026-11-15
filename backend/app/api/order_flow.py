from fastapi import APIRouter, HTTPException, Query

from app.schemas.order_flow import DerivativesContextResponse, OrderFlowResponse
from app.services.analysis.order_flow import analyze_order_flow
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.binance_futures import BinanceFuturesMarketData

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
        candles = await BinanceMarketData().fetch_klines(
            symbol, interval, lookback, closed_only=True
        )
        result = analyze_order_flow(candles, lookback)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderFlowResponse(**result)


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
