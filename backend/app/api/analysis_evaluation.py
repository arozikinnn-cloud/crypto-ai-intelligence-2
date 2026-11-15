import asyncio

from fastapi import APIRouter, HTTPException, Query

from app.schemas.combined_backtest import (
    CombinedBacktestResponse,
    TimeframePerformanceResponse,
)
from app.services.analysis.combined_backtest import run_combined_backtest
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData

router = APIRouter(prefix="/analysis", tags=["signal evaluation"])

VALID_INTERVALS = ("5m", "15m", "30m", "1h", "4h", "1d")


@router.get("/intelligence/backtest", response_model=CombinedBacktestResponse)
async def intelligence_backtest(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    interval: str = Query(default="1h"),
    limit: int = Query(default=500, ge=140, le=1000),
    horizon: int = Query(default=3, ge=1, le=24),
    fee_bps: float = Query(default=10.0, ge=0, le=100),
    slippage_bps: float = Query(default=5.0, ge=0, le=100),
) -> CombinedBacktestResponse:
    if interval not in VALID_INTERVALS:
        raise HTTPException(status_code=422, detail="Unsupported timeframe.")
    try:
        candles = await BinanceMarketData().fetch_klines(symbol, interval, limit, closed_only=True)
        return CombinedBacktestResponse(**run_combined_backtest(
            candles, fee_bps=fee_bps, slippage_bps=slippage_bps, horizon=horizon
        ))
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/intelligence/timeframe-performance", response_model=TimeframePerformanceResponse)
async def timeframe_performance(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    intervals: str = Query(default="15m,1h,4h"),
    limit: int = Query(default=500, ge=140, le=1000),
    horizon: int = Query(default=3, ge=1, le=24),
) -> TimeframePerformanceResponse:
    selected = [part.strip() for part in intervals.split(",") if part.strip()]
    if not selected or len(selected) > 4 or len(set(selected)) != len(selected):
        raise HTTPException(status_code=422, detail="Provide 1–4 unique timeframes.")
    if any(item not in VALID_INTERVALS for item in selected):
        raise HTTPException(status_code=422, detail="Unsupported timeframe.")
    try:
        market = BinanceMarketData()
        candle_sets = await asyncio.gather(*(
            market.fetch_klines(symbol, interval, limit, closed_only=True)
            for interval in selected
        ))
        results = [
            CombinedBacktestResponse(**run_combined_backtest(items, horizon=horizon))
            for items in candle_sets
        ]
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TimeframePerformanceResponse(
        symbol=symbol.upper(),
        results=results,
        note="Perbandingan memakai jumlah candle dan horizon candle yang sama, bukan durasi kalender yang sama. Bandingkan juga jumlah trade dan kualitas out-of-sample.",
    )
