import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.liquidations import LiquidationHistoryResponse
from app.services.market_data.liquidation_storage import read_liquidation_history

from app.schemas.liquidations import LiquidationEvent
from app.services.market_data.liquidations import normalize_liquidation_message

router = APIRouter(prefix="/analysis", tags=["liquidation stream"])


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

        async with websockets.connect(
            url, ping_interval=20, ping_timeout=20
        ) as upstream:
            while True:
                try:
                    raw = await asyncio.wait_for(upstream.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                message = json.loads(raw)
                event = normalize_liquidation_message(message)
                await websocket.send_json(
                    LiquidationEvent(**event).model_dump(mode="json")
                )
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        raise
    except Exception:
        try:
            await websocket.close(
                code=1011, reason="Liquidation stream disconnected"
            )
        except Exception:
            pass



@router.get("/liquidations/history", response_model=LiquidationHistoryResponse)
def liquidation_history(
    symbol: str = Query(
        default="BTCUSDT", min_length=5, max_length=20, pattern="^[A-Za-z0-9]+$"
    ),
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> LiquidationHistoryResponse:
    try:
        result = read_liquidation_history(db, symbol, hours)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LiquidationHistoryResponse(**result)
