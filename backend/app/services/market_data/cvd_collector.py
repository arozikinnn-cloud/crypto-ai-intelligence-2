import asyncio
import json
import logging
import websockets

from app.database.session import SessionLocal
from app.services.market_data.cvd_collector_storage import persist_aggtrade_events

logger = logging.getLogger(__name__)


def normalize_aggtrade_event(message: dict, expected_symbol: str) -> dict:
    try:
        symbol = str(message["s"]).upper()
        trade_id = int(message["a"])
        timestamp = int(message["T"])
        quantity = float(message["q"])
        buyer_is_maker = message["m"]
        if symbol != expected_symbol:
            raise ValueError("Unexpected stream symbol.")
        if trade_id < 0 or timestamp <= 0 or quantity <= 0:
            raise ValueError("Invalid trade id, timestamp, or quantity.")
        if not isinstance(buyer_is_maker, bool):
            raise ValueError("Invalid buyer-maker flag.")
        return {
            "trade_id": trade_id,
            "timestamp": timestamp,
            "quantity": quantity,
            "buyer_is_maker": buyer_is_maker,
        }
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Malformed Binance aggTrade websocket event.") from exc


async def stream_binance_aggtrades(
    symbol: str,
    stop_event: asyncio.Event,
    flush_interval: float = 2.0,
) -> None:
    """Collect public spot aggTrades, batch to DB, and reconnect with backoff."""
    normalized = symbol.upper().strip()
    if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
        raise ValueError("Invalid CVD collector symbol.")

    url = f"wss://stream.binance.com:9443/ws/{normalized.lower()}@aggTrade"
    delay = 1
    pending: list[dict] = []
    last_flush = asyncio.get_running_loop().time()

    async def flush() -> None:
        nonlocal pending, last_flush
        if not pending:
            last_flush = asyncio.get_running_loop().time()
            return
        batch, pending = pending, []
        db = SessionLocal()
        try:
            persist_aggtrade_events(db, normalized, batch)
        except Exception:
            logger.exception("CVD batch persistence failed for %s", normalized)
            pending = batch + pending
        finally:
            db.close()
            last_flush = asyncio.get_running_loop().time()

    while not stop_event.is_set():
        try:
            async with websockets.connect(
                url, ping_interval=20, ping_timeout=20, close_timeout=5
            ) as socket:
                logger.info("CVD aggTrades stream connected for %s", normalized)
                delay = 1
                while not stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(socket.recv(), timeout=1.0)
                    except asyncio.TimeoutError:
                        if asyncio.get_running_loop().time() - last_flush >= flush_interval:
                            await flush()
                        continue
                    try:
                        message = json.loads(raw)
                        if isinstance(message, dict):
                            pending.append(normalize_aggtrade_event(message, normalized))
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Ignoring malformed aggTrade event for %s", normalized)
                    if asyncio.get_running_loop().time() - last_flush >= flush_interval:
                        await flush()
        except asyncio.CancelledError:
            await flush()
            raise
        except Exception:
            logger.exception("CVD websocket disconnected for %s; reconnecting", normalized)
            await flush()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                delay = min(delay * 2, 30)

    await flush()
