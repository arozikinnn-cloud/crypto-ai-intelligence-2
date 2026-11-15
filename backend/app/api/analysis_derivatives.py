import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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
