import asyncio
import json
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from app.schemas.order_flow import DerivativesContextResponse, OrderFlowResponse
from app.schemas.liquidations import LiquidationEvent
from app.services.analysis.order_flow import analyze_order_flow
from app.services.market_data.base import MarketDataError
from app.services.market_data.binance import BinanceMarketData
from app.services.market_data.binance_futures import BinanceFuturesMarketData
from app.services.market_data.liquidations import normalize_liquidation_message

router = APIRouter(prefix="/analysis", tags=["order-flow-and-derivatives"])


@router.get("/order-flow", response_model=OrderFlowResponse)
async def order_flow_analysis(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    interval: str = Query(default="5m"),
    limit: int = Query(default=100, ge=2, le=500),
) -> OrderFlowResponse:
    try:
        candles = await BinanceMarketData().fetch_klines(symbol, interval, limit)
        result = analyze_order_flow(candles, lookback=min(100, limit))
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return OrderFlowResponse(
        symbol=symbol.upper(),
        timeframe=interval,
        **result,
    )


@router.get("/derivatives", response_model=DerivativesContextResponse)
async def derivatives_context(
    symbol: str = Query(default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"),
    period: str = Query(default="5m"),
) -> DerivativesContextResponse:
    try:
        result = await BinanceFuturesMarketData().fetch_derivatives_context(symbol, period)
    except MarketDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return DerivativesContextResponse(**result)


@router.websocket("/liquidations/stream")
async def liquidation_stream(websocket: WebSocket, symbol: str = "BTCUSDT"):
    normalized = symbol.upper().strip()
    if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
        await websocket.close(code=1008, reason="Invalid symbol")
        return
    await websocket.accept()
    url = f"wss://fstream.binance.com/ws/{normalized.lower()}@forceOrder"
    try:
        import websockets
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as upstream:
            while True:
                try:
                    raw = await asyncio.wait_for(upstream.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                message = json.loads(raw)
                event = normalize_liquidation_message(message)
                await websocket.send_json(LiquidationEvent(**event).model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        raise
    except Exception:
        try:
            await websocket.close(code=1011, reason="Liquidation stream disconnected")
        except Exception:
            pass
