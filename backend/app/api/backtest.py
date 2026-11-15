from fastapi import APIRouter, HTTPException, Query
from app.schemas.backtest import BacktestResponse
from app.services.analysis.backtest import run_ema_backtest
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData

router = APIRouter(prefix="/analysis", tags=["backtesting"])


@router.get("/backtest", response_model=BacktestResponse)
async def backtest(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    interval: str = Query(default="1h"),
    limit: int = Query(default=500, ge=120, le=1000),
    fee_bps: float = Query(default=10.0, ge=0, le=100),
    slippage_bps: float = Query(default=5.0, ge=0, le=100),
) -> BacktestResponse:
    try:
        candles = await BinanceMarketData().fetch_klines(symbol, interval, limit)
        result = run_ema_backtest(candles, fee_bps=fee_bps, slippage_bps=slippage_bps)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return BacktestResponse(**result)
