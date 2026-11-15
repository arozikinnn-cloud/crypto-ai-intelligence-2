from datetime import datetime, timezone
import httpx
from app.services.market_data.base import MarketDataError, NormalizedCandle
from app.services.market_data.quality import validate_candles


class BinanceMarketData:
    BASE_URL = "https://api.binance.com"
    ALLOWED_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"}

    async def fetch_klines(self, symbol: str, interval: str, limit: int = 200) -> list[NormalizedCandle]:
        normalized_symbol = symbol.upper().strip()
        if not normalized_symbol.isalnum() or not 5 <= len(normalized_symbol) <= 20:
            raise MarketDataError("Invalid trading symbol.")
        if interval not in self.ALLOWED_INTERVALS:
            raise MarketDataError("Unsupported candle interval.")
        if not 1 <= limit <= 1000:
            raise MarketDataError("Limit must be between 1 and 1000.")

        try:
            async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
                response = await client.get(
                    "/api/v3/klines",
                    params={"symbol": normalized_symbol, "interval": interval, "limit": limit},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("Binance market-data request failed.") from exc

        if not isinstance(payload, list):
            raise MarketDataError("Unexpected exchange response format.")

        candles = []
        try:
            for row in payload:
                if not isinstance(row, list) or len(row) < 8:
                    raise ValueError("Malformed kline row")
                candles.append(
                    NormalizedCandle(
                        symbol=normalized_symbol,
                        timeframe=interval,
                        open_time=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                        close_time=datetime.fromtimestamp(int(row[6]) / 1000, tz=timezone.utc),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        quote_volume=float(row[7]),
                        trades=int(row[8]) if len(row) > 8 else 0,
                    )
                )
        except (TypeError, ValueError, IndexError, OverflowError) as exc:
            raise MarketDataError("Binance returned malformed candle data.") from exc

        validate_candles(candles)
        return candles
