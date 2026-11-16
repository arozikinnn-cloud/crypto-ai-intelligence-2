from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.market import CandleResponse, MarketDataResponse
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.storage import store_candles

router = APIRouter(prefix="/market", tags=["market-data"])


@router.get(
    "/candles",
    response_model=MarketDataResponse,
    summary="Fetch and store public exchange candles",
)
async def get_candles(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    interval: str = Query(default="1h"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> MarketDataResponse:
    provider = BinanceMarketData()
    try:
        candles = await provider.fetch_klines(symbol, interval, limit)
        stored = store_candles(db, "binance", candles)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    return MarketDataResponse(
        provider="binance",
        symbol=symbol.upper(),
        timeframe=interval,
        count=len(candles),
        stored=stored,
        candles=[CandleResponse(**asdict(candle)) for candle in candles],
    )
