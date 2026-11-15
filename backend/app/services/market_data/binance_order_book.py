from math import isfinite

import httpx
from app.services.market_data.http import get_json_with_retry

from app.services.market_data.base import MarketDataError


class BinanceOrderBookMarketData:
    """Public Spot depth snapshot; this is a snapshot, not historical order flow."""

    BASE_URL = "https://api.binance.com"
    ALLOWED_LIMITS = {5, 10, 20, 50, 100, 500, 1000}

    async def fetch_order_book(self, symbol: str, limit: int = 100) -> dict:
        normalized = symbol.upper().strip()
        if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
            raise MarketDataError("Invalid trading symbol.")
        if limit not in self.ALLOWED_LIMITS:
            raise MarketDataError("Unsupported order-book depth limit.")
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
            payload = await get_json_with_retry(
                client,
                "/api/v3/depth",
                {"symbol": normalized, "limit": limit},
                "Binance order book",
            )

        try:
            bids = [[float(price), float(quantity)] for price, quantity in payload["bids"]]
            asks = [[float(price), float(quantity)] for price, quantity in payload["asks"]]
            if not bids or not asks:
                raise ValueError("Empty order book.")
            if any(
                not isfinite(price) or not isfinite(quantity) or price <= 0 or quantity < 0
                for level in bids + asks
                for price, quantity in [level]
            ):
                raise ValueError("Invalid order-book level.")
            bids.sort(key=lambda level: level[0], reverse=True)
            asks.sort(key=lambda level: level[0])
            if bids[0][0] >= asks[0][0]:
                raise ValueError("Crossed order book.")
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise MarketDataError("Binance returned malformed order-book data.") from exc

        return {"symbol": normalized, "bids": bids, "asks": asks, "limit": limit}
