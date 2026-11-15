import asyncio
import json
import logging

import websockets

from app.database.session import SessionLocal
from app.services.market_data.liquidation_storage import persist_liquidation_events
from app.services.market_data.liquidations import normalize_liquidation_message

logger = logging.getLogger(__name__)


async def stream_binance_liquidations(
    symbol: str, stop_event: asyncio.Event, flush_interval: float = 2.0
) -> None:
    normalized = symbol.upper().strip()
    if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
        raise ValueError("Invalid liquidation collector symbol.")

    url = f"wss://fstream.binance.com/ws/{normalized.lower()}@forceOrder"
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
            persist_liquidation_events(db, batch)
        except Exception:
            logger.exception("Liquidation persistence failed for %s", normalized)
            pending = batch + pending
        finally:
            db.close()
            last_flush = asyncio.get_running_loop().time()

    while not stop_event.is_set():
        try:
            async with websockets.connect(
                url, ping_interval=20, ping_timeout=20, close_timeout=5
            ) as socket:
                logger.info("Liquidation stream connected for %s", normalized)
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
                        event = normalize_liquidation_message(message)
                        pending.append(
                            {
                                key: event[key]
                                for key in (
                                    "event_key",
                                    "symbol",
                                    "side",
                                    "price",
                                    "quantity",
                                    "notional",
                                    "timestamp",
                                )
                            }
                        )
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Ignoring malformed liquidation event for %s", normalized)
                    if asyncio.get_running_loop().time() - last_flush >= flush_interval:
                        await flush()
        except asyncio.CancelledError:
            await flush()
            raise
        except Exception:
            logger.exception("Liquidation stream disconnected for %s; reconnecting", normalized)
            await flush()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                delay = min(delay * 2, 30)

    await flush()
