import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from app.services.market_data.base import MarketDataError, NormalizedCandle
from app.services.market_data.quality import validate_candles

logger = logging.getLogger(__name__)


def normalize_kline_message(message: dict) -> NormalizedCandle:
    try:
        payload = message["k"]
        candle = NormalizedCandle(
            symbol=str(payload["s"]).upper(),
            timeframe=str(payload["i"]),
            open_time=datetime.fromtimestamp(int(payload["t"]) / 1000, tz=timezone.utc),
            close_time=datetime.fromtimestamp(int(payload["T"]) / 1000, tz=timezone.utc),
            open=float(payload["o"]),
            high=float(payload["h"]),
            low=float(payload["l"]),
            close=float(payload["c"]),
            volume=float(payload["v"]),
            quote_volume=float(payload["q"]),
            trades=int(payload["n"]),
            taker_buy_volume=float(payload["V"]) if "V" in payload else None,
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise MarketDataError("Binance returned malformed websocket kline data.") from exc
    validate_candles([candle])
    return candle


async def stream_binance_klines(
    symbol: str,
    interval: str,
    on_candle: Callable[[NormalizedCandle], Awaitable[None]],
    stop_event: asyncio.Event,
) -> None:
    """Consume normalized public kline updates; caller controls lifecycle via stop_event."""
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
                        await on_candle(normalize_kline_message(message))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Binance websocket disconnected; reconnecting")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                delay = min(delay * 2, 30)
