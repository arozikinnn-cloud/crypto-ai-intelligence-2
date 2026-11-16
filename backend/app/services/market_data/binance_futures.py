import asyncio
from math import isfinite
import httpx
import logging
from app.services.market_data.base import MarketDataError


logger = logging.getLogger(__name__)


class BinanceFuturesMarketData:
    # Binance Futures is geo-restricted (HTTP 451) from some Vercel regions.
    # Use Bybit's public linear-perpetual market endpoints as a read-only fallback.
    BASE_URL = "https://api.bybit.com"
    PERIOD_MAP = {
        "5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h",
        "2h": "2h", "4h": "4h", "6h": "6h", "12h": "12h", "1d": "1d",
    }
    ALLOWED_PERIODS = set(PERIOD_MAP)

    async def fetch_derivatives_context(self, symbol: str, period: str = "5m") -> dict:
        normalized = symbol.upper().strip()
        if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
            raise MarketDataError("Invalid trading symbol.")
        if period not in self.ALLOWED_PERIODS:
            raise MarketDataError("Unsupported open-interest period.")

        params_oi = {
            "category": "linear", "symbol": normalized,
            "intervalTime": self.PERIOD_MAP[period], "limit": "2",
        }
        params_funding = {"category": "linear", "symbol": normalized, "limit": "1"}

        try:
            async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
                oi_response, funding_response = await asyncio.gather(
                    client.get("/v5/market/open-interest", params=params_oi),
                    client.get("/v5/market/funding/history", params=params_funding),
                )
                oi_response.raise_for_status()
                funding_response.raise_for_status()
                oi_payload = oi_response.json()
                funding_payload = funding_response.json()
            if oi_payload.get("retCode") != 0 or funding_payload.get("retCode") != 0:
                raise ValueError("Bybit public market API returned an error.")
            oi_rows = oi_payload["result"]["list"]
            funding_rows = funding_payload["result"]["list"]
            if not oi_rows or not funding_rows:
                raise ValueError("Missing derivatives history.")
            latest_oi = float(oi_rows[0]["openInterest"])
            previous_oi = float(oi_rows[1]["openInterest"]) if len(oi_rows) > 1 else None
            funding_rate = float(funding_rows[0]["fundingRate"])
            funding_time = int(funding_rows[0]["fundingRateTimestamp"])
            if not isfinite(latest_oi) or latest_oi < 0:
                raise ValueError("Invalid open interest.")
            if previous_oi is not None and (not isfinite(previous_oi) or previous_oi < 0):
                raise ValueError("Invalid previous open interest.")
            if not isfinite(funding_rate):
                raise ValueError("Invalid funding rate.")
            oi_change = (
                (latest_oi - previous_oi) / previous_oi * 100
                if previous_oi not in (None, 0) else None
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, OverflowError) as exc:
            logger.warning("Bybit derivatives fetch failed: %r", exc)
            raise MarketDataError(
                "Public derivatives data provider failed or returned malformed data."
            ) from exc

        return {
            "symbol": normalized,
            "source_market": "bybit_linear_perpetual",
            "open_interest_unit": "contracts",
            "open_interest": latest_oi,
            "open_interest_change_percent": oi_change,
            "open_interest_period": period,
            "funding_rate": funding_rate,
            "funding_time": funding_time,
            "interpretation": (
                "OI mengukur jumlah kontrak terbuka; kenaikan OI tidak otomatis bullish. "
                "Funding positif berarti long membayar short; funding negatif berarti "
                "short membayar long. Data derivatif berasal dari Bybit linear perpetual, "
                "bukan Binance Futures. Gunakan bersama harga, volume, dan konteks lain."
            ),
        }
