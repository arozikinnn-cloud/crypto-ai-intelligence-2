from fastapi import APIRouter, HTTPException, Query

from app.schemas.order_book import OrderBookAnalysisResponse
from app.services.analysis.order_book import analyze_order_book
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance_order_book import BinanceOrderBookMarketData

router = APIRouter(prefix="/analysis", tags=["order book"])


@router.get("/order-book", response_model=OrderBookAnalysisResponse)
async def order_book_analysis(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    limit: int = Query(default=100, ge=5, le=1000),
    depth_levels: int = Query(default=20, ge=1, le=100),
) -> OrderBookAnalysisResponse:
    if limit not in BinanceOrderBookMarketData.ALLOWED_LIMITS:
        raise HTTPException(status_code=422, detail="Unsupported order-book depth limit.")
    try:
        snapshot = await BinanceOrderBookMarketData().fetch_order_book(symbol, limit)
        return OrderBookAnalysisResponse(**analyze_order_book(snapshot, depth_levels))
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
