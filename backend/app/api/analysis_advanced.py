import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from app.schemas.multi_timeframe import MultiTimeframeResponse
from app.schemas.structure import StructureResponse
from app.services.analysis.engine import analyze_market
from app.services.analysis.structure import analyze_structure
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData

router = APIRouter(prefix="/analysis", tags=["advanced analysis"])
VALID_INTERVALS = BinanceMarketData.ALLOWED_INTERVALS


@router.get("/multi-timeframe", response_model=MultiTimeframeResponse)
async def multi_timeframe_analysis(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    intervals: str = Query(default="15m,1h,4h"),
    limit: int = Query(default=200, ge=60, le=500),
) -> MultiTimeframeResponse:
    selected = [item.strip() for item in intervals.split(",") if item.strip()]
    if not selected or len(selected) > 4 or len(set(selected)) != len(selected):
        raise HTTPException(status_code=422, detail="Provide 1–4 unique comma-separated intervals.")
    if any(item not in VALID_INTERVALS for item in selected):
        raise HTTPException(status_code=422, detail="One or more intervals are unsupported.")
    try:
        provider = BinanceMarketData()
        candle_sets = await asyncio.gather(
            *(provider.fetch_klines(symbol, interval, limit) for interval in selected)
        )
        analyses = [analyze_market(items) for items in candle_sets]
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    sides = [item["side"] for item in analyses]
    active_sides = [side for side in sides if side in {"BUY", "SELL"}]
    overall = active_sides[0] if len(active_sides) == len(sides) and len(set(active_sides)) == 1 else "NO TRADE"
    reasons = (
        [f"Semua {len(selected)} timeframe sepakat {overall}."]
        if overall != "NO TRADE"
        else ["Timeframe belum seluruhnya memberi sinyal searah; hindari memaksakan entry."]
    )
    return MultiTimeframeResponse(
        symbol=symbol.upper(),
        timestamp=datetime.now(timezone.utc),
        overall_side=overall,
        aligned_timeframes=len(active_sides) if overall != "NO TRADE" else 0,
        total_timeframes=len(selected),
        analyses=analyses,
        reasons=reasons,
    )


@router.get("/structure", response_model=StructureResponse)
async def market_structure_analysis(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    interval: str = Query(default="1h"),
    limit: int = Query(default=200, ge=60, le=500),
) -> StructureResponse:
    if interval not in VALID_INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported candle interval.")
    try:
        candles = await BinanceMarketData().fetch_klines(symbol, interval, limit)
        result = analyze_structure(candles)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StructureResponse(
        symbol=symbol.upper(),
        timeframe=interval,
        timestamp=datetime.now(timezone.utc),
        **result,
    )
