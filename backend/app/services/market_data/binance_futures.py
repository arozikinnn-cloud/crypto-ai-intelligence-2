import httpx
from app.services.market_data.base import MarketDataError


class BinanceFuturesMarketData:
    BASE_URL = "https://fapi.binance.com"
    ALLOWED_PERIODS = {"5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d"}

    async def fetch_derivatives_context(self, symbol: str, period: str = "5m") -> dict:
        normalized = symbol.upper().strip()
        if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
            raise MarketDataError("Invalid trading symbol.")
        if period not in self.ALLOWED_PERIODS:
            raise MarketDataError("Unsupported open-interest period.")

        try:
            async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
                oi_response, funding_response = await __import__("asyncio").gather(
                    client.get(
                        "/futures/data/openInterestHist",
                        params={"symbol": normalized, "period": period, "limit": 2},
                    ),
                    client.get(
                        "/fapi/v1/fundingRate",
                        params={"symbol": normalized, "limit": 1},
                    ),
                )
                oi_response.raise_for_status()
                funding_response.raise_for_status()
                oi_payload = oi_response.json()
                funding_payload = funding_response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("Binance Futures derivatives request failed.") from exc

        try:
            if not isinstance(oi_payload, list) or len(oi_payload) < 1:
                raise ValueError("Missing open-interest history.")
            latest_oi = float(oi_payload[-1]["sumOpenInterest"])
            previous_oi = float(oi_payload[-2]["sumOpenInterest"]) if len(oi_payload) > 1 else None
            oi_change = (
                (latest_oi - previous_oi) / previous_oi * 100
                if previous_oi not in (None, 0)
                else None
            )
            if not isinstance(funding_payload, list) or not funding_payload:
                raise ValueError("Missing funding-rate history.")
            funding_rate = float(funding_payload[-1]["fundingRate"])
            funding_time = int(funding_payload[-1]["fundingTime"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            raise MarketDataError("Binance Futures returned malformed derivatives data.") from exc

        return {
            "symbol": normalized,
            "open_interest": latest_oi,
            "open_interest_change_percent": oi_change,
            "open_interest_period": period,
            "funding_rate": funding_rate,
            "funding_time": funding_time,
            "interpretation": (
                "OI naik menunjukkan posisi terbuka bertambah, bukan otomatis bullish. "
                "Funding positif berarti long membayar short; negatif berarti short membayar long."
            ),
        }
