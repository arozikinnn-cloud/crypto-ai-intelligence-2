from math import isfinite
import httpx

from app.services.market_data.base import MarketDataError


class BinanceAggTradesMarketData:
    """Trade-level aggressor-volume proxy from Binance public aggregated trades."""

    BASE_URL = "https://api.binance.com"

    async def fetch_order_flow(self, symbol: str, limit: int = 500) -> dict:
        normalized = symbol.upper().strip()
        if not normalized.isalnum() or not 5 <= len(normalized) <= 20:
            raise MarketDataError("Invalid trading symbol.")
        if not 10 <= limit <= 1000:
            raise MarketDataError("AggTrades limit must be between 10 and 1000.")

        try:
            async with httpx.AsyncClient(base_url=self.BASE_URL, timeout=12.0) as client:
                response = await client.get(
                    "/api/v3/aggTrades",
                    params={"symbol": normalized, "limit": limit},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError("Binance aggregated-trades request failed.") from exc

        if not isinstance(payload, list) or not payload:
            raise MarketDataError("Binance returned no aggregated-trades data.")

        buy_volume = 0.0
        sell_volume = 0.0
        first_time = None
        last_time = None
        try:
            previous_id = None
            for trade in payload:
                trade_id = int(trade["a"])
                timestamp = int(trade["T"])
                quantity = float(trade["q"])
                buyer_is_maker = trade["m"]
                if not isinstance(buyer_is_maker, bool):
                    raise ValueError("Invalid aggressor-side flag.")
                if not isfinite(quantity) or quantity <= 0:
                    raise ValueError("Invalid aggregated-trade quantity.")
                if previous_id is not None and trade_id <= previous_id:
                    raise ValueError("Aggregated trades are not strictly ordered.")
                previous_id = trade_id
                # If buyer is maker, seller was the aggressor; otherwise buyer was.
                if buyer_is_maker:
                    sell_volume += quantity
                else:
                    buy_volume += quantity
                first_time = timestamp if first_time is None else first_time
                last_time = timestamp
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise MarketDataError("Binance returned malformed aggregated-trades data.") from exc

        total = buy_volume + sell_volume
        delta = buy_volume - sell_volume
        delta_percent = delta / total * 100 if total else 0.0
        if delta_percent >= 5:
            bias = "BUY_PRESSURE"
        elif delta_percent <= -5:
            bias = "SELL_PRESSURE"
        else:
            bias = "BALANCED"

        return {
            "symbol": normalized,
            "source_market": "binance_spot_aggtrades",
            "trade_count": len(payload),
            "buy_aggressor_volume": buy_volume,
            "sell_aggressor_volume": sell_volume,
            "net_delta": delta,
            "delta_percent": delta_percent,
            "cumulative_delta": delta,
            "bias": bias,
            "first_trade_time": first_time,
            "last_trade_time": last_time,
            "method_note": (
                "Delta dihitung dari kuantitas Binance aggregated trades: buyer aggressor "
                "ketika buyer bukan maker; seller aggressor ketika buyer adalah maker. "
                "Ini data trade-level agregat untuk batch terbaru, bukan full-session CVD, "
                "DOM, footprint, atau order-book absorption."
            ),
        }
