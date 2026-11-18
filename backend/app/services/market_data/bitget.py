from datetime import datetime, timedelta, timezone
from math import isfinite

import httpx

from app.services.market_data.base import MarketDataError, NormalizedCandle
from app.services.market_data.http import get_json_with_retry
from app.services.market_data.quality import validate_candles


class BitgetUsdtFuturesMarketData:
    """Read-only Bitget USDT-M Futures market data; no private API key required."""

    BASE_URL = "https://api.bitget.com"
    PRODUCT_TYPE = "USDT-FUTURES"
    INTERVALS = {
        "1m": ("1m", timedelta(minutes=1)),
        "3m": ("3m", timedelta(minutes=3)),
        "5m": ("5m", timedelta(minutes=5)),
        "15m": ("15m", timedelta(minutes=15)),
        "30m": ("30m", timedelta(minutes=30)),
        "1h": ("1H", timedelta(hours=1)),
        "2h": ("2H", timedelta(hours=2)),
        "4h": ("4H", timedelta(hours=4)),
        "6h": ("6H", timedelta(hours=6)),
        "12h": ("12H", timedelta(hours=12)),
        "1d": ("1D", timedelta(days=1)),
        "3d": ("3D", timedelta(days=3)),
        "1w": ("1W", timedelta(weeks=1)),
    }

    @staticmethod
    def _symbol(value: str) -> str:
        normalized = value.upper().strip()
        if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
            raise MarketDataError("Invalid trading symbol.")
        return normalized

    @staticmethod
    def _data(payload: object, source: str):
        if not isinstance(payload, dict) or payload.get("code") != "00000":
            message = payload.get("msg") if isinstance(payload, dict) else None
            raise MarketDataError(f"{source} rejected the request: {message or 'invalid response'}.")
        if "data" not in payload:
            raise MarketDataError(f"{source} returned no data field.")
        return payload["data"]

    async def fetch_klines(
        self, symbol: str, interval: str, limit: int = 200, closed_only: bool = False
    ) -> list[NormalizedCandle]:
        normalized = self._symbol(symbol)
        if interval not in self.INTERVALS:
            raise MarketDataError("Unsupported Bitget candle interval.")
        if not 1 <= limit <= 1000:
            raise MarketDataError("Limit must be between 1 and 1000.")
        bitget_interval, duration = self.INTERVALS[interval]

        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
            payload = await get_json_with_retry(
                client,
                "/api/v2/mix/market/candles",
                {
                    "symbol": normalized,
                    "productType": self.PRODUCT_TYPE,
                    "granularity": bitget_interval,
                    "limit": str(limit),
                },
                "Bitget USDT-M Futures candles",
            )

        rows = self._data(payload, "Bitget candles")
        if not isinstance(rows, list):
            raise MarketDataError("Bitget returned malformed candle data.")
        candles = []
        try:
            for row in rows:
                if not isinstance(row, list) or len(row) < 7:
                    raise ValueError("Malformed candle row")
                opened = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
                candles.append(
                    NormalizedCandle(
                        symbol=normalized,
                        timeframe=interval,
                        open_time=opened,
                        close_time=opened + duration - timedelta(milliseconds=1),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        quote_volume=float(row[6]),
                        trades=0,
                    )
                )
            candles.sort(key=lambda candle: candle.open_time)
            validate_candles(candles)
        except (TypeError, ValueError, IndexError, OverflowError) as exc:
            raise MarketDataError("Bitget returned malformed candle data.") from exc

        if closed_only:
            now = datetime.now(timezone.utc)
            candles = [candle for candle in candles if candle.close_time < now]
        return candles

    async def fetch_order_book(self, symbol: str, limit: int = 100) -> dict:
        normalized = self._symbol(symbol)
        if not 1 <= limit <= 1000:
            raise MarketDataError("Order-book limit must be between 1 and 1000.")
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
            payload = await get_json_with_retry(
                client,
                "/api/v3/market/orderbook",
                {"category": self.PRODUCT_TYPE, "symbol": normalized, "limit": str(limit)},
                "Bitget USDT-M Futures order book",
            )
        data = self._data(payload, "Bitget order book")
        try:
            bids = [[float(p), float(q)] for p, q in data["b"]]
            asks = [[float(p), float(q)] for p, q in data["a"]]
            if not bids or not asks:
                raise ValueError("Empty order book.")
            levels = bids + asks
            if any(
                not isfinite(price) or not isfinite(size) or price <= 0 or size < 0
                for price, size in levels
            ):
                raise ValueError("Invalid order-book level.")
            bids.sort(key=lambda item: item[0], reverse=True)
            asks.sort(key=lambda item: item[0])
            if bids[0][0] >= asks[0][0]:
                raise ValueError("Crossed order book.")
            timestamp = int(data.get("ts", payload.get("requestTime", 0)))
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
            raise MarketDataError("Bitget returned malformed order-book data.") from exc
        return {
            "symbol": normalized,
            "provider": "bitget_usdt_futures",
            "bids": bids,
            "asks": asks,
            "timestamp": timestamp,
            "limit": limit,
        }

    async def fetch_derivatives_context(self, symbol: str) -> dict:
        normalized = self._symbol(symbol)
        params = {"symbol": normalized, "productType": self.PRODUCT_TYPE}
        async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
            oi_payload, funding_payload = await __import__("asyncio").gather(
                get_json_with_retry(
                    client, "/api/v2/mix/market/open-interest", params,
                    "Bitget USDT-M Futures open interest",
                ),
                get_json_with_retry(
                    client, "/api/v2/mix/market/current-fund-rate", params,
                    "Bitget USDT-M Futures funding rate",
                ),
            )
        oi_data = self._data(oi_payload, "Bitget open interest")
        funding_data = self._data(funding_payload, "Bitget funding rate")
        try:
            oi_rows = oi_data["openInterestList"]
            funding_row = funding_data[0] if isinstance(funding_data, list) else funding_data
            if not oi_rows or not isinstance(funding_row, dict):
                raise ValueError("Missing derivatives data.")
            open_interest = float(oi_rows[0]["size"])
            funding_rate = float(funding_row["fundingRate"])
            if not isfinite(open_interest) or open_interest < 0 or not isfinite(funding_rate):
                raise ValueError("Invalid derivatives value.")
            oi_timestamp = int(oi_data.get("ts", 0))
            funding_time = funding_row.get("fundingTime") or funding_row.get("nextUpdate")
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
            raise MarketDataError("Bitget returned malformed derivatives data.") from exc
        return {
            "symbol": normalized,
            "provider": "bitget_usdt_futures",
            "open_interest": open_interest,
            "open_interest_unit": "base_asset",
            "open_interest_timestamp": oi_timestamp,
            "funding_rate": funding_rate,
            "funding_time": funding_time,
        }
