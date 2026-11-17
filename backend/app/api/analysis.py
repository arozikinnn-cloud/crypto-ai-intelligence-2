from fastapi import APIRouter, HTTPException, Query
from app.schemas.analysis import AnalysisResponse
from app.services.analysis.engine import analyze_market
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/technical", response_model=AnalysisResponse)
async def technical_analysis(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    interval: str = Query(default="15m"),
    limit: int = Query(default=200, ge=60, le=1000),
) -> AnalysisResponse:
    try:
        candles = await BinanceMarketData().fetch_klines(symbol, interval, limit, closed_only=True)
        result = analyze_market(candles)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnalysisResponse(**result)
