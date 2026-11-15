import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from app.services.market_data.base import MarketDataError

logger = logging.getLogger(__name__)


async def stream_binance_klines(
    symbol: str,
    interval: str,
    on_message: Callable[[dict], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    """Consume Binance public kline updates; caller controls lifecycle via stop_event."""
    try:
        import websockets
    except ImportError as exc:
        message = "Install the optional websockets dependency to use streaming."
        raise MarketDataError(message) from exc

    stream = f"{symbol.lower()}@kline_{interval}"
    url = f"wss://stream.binance.com:9443/ws/{stream}"
    delay = 1
    while not stop_event.is_set():
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as socket:
                delay = 1
                while not stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(socket.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        continue
                    message = json.loads(raw)
                    if isinstance(message, dict) and isinstance(message.get("k"), dict):
                        await on_message(message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Binance websocket disconnected; reconnecting")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                delay = min(delay * 2, 30)
