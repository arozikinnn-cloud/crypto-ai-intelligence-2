from math import isfinite
import httpx

from app.services.market_data.base import MarketDataError


class BinanceAggTradesMarketData:
    """Trade-level aggressor-volume proxy from Binance public aggregated trades."""

    BASE_URL = "https://api.binance.com"
    BUCKET_MS = 60_000

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
        previous_id = None
        buckets: dict[int, dict] = {}
        try:
            for trade in payload:
                trade_id = int(trade["a"])
                timestamp = int(trade["T"])
                quantity = float(trade["q"])
                buyer_is_maker = trade["m"]
                if not isinstance(buyer_is_maker, bool):
                    raise ValueError("Invalid aggressor-side flag.")
                if timestamp <= 0 or not isfinite(quantity) or quantity <= 0:
                    raise ValueError("Invalid aggregated-trade timestamp or quantity.")
                if previous_id is not None and trade_id <= previous_id:
                    raise ValueError("Aggregated trades are not strictly ordered.")
                previous_id = trade_id

                # If buyer is maker, seller was the aggressor; otherwise buyer was.
                buy = 0.0 if buyer_is_maker else quantity
                sell = quantity if buyer_is_maker else 0.0
                buy_volume += buy
                sell_volume += sell
                bucket_time = timestamp // self.BUCKET_MS * self.BUCKET_MS
                bucket = buckets.setdefault(
                    bucket_time,
                    {"buy_volume": 0.0, "sell_volume": 0.0, "trade_count": 0},
                )
                bucket["buy_volume"] += buy
                bucket["sell_volume"] += sell
                bucket["trade_count"] += 1
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

        cvd = 0.0
        cvd_points = []
        for bucket_time in sorted(buckets):
            bucket = buckets[bucket_time]
            bucket_delta = bucket["buy_volume"] - bucket["sell_volume"]
            cvd += bucket_delta
            cvd_points.append(
                {
                    "bucket_start_time": bucket_time,
                    "buy_volume": bucket["buy_volume"],
                    "sell_volume": bucket["sell_volume"],
                    "delta": bucket_delta,
                    "cumulative_delta": cvd,
                    "trade_count": bucket["trade_count"],
                }
            )

        return {
            "symbol": normalized,
            "source_market": "binance_spot_aggtrades",
            "trade_count": len(payload),
            "buy_aggressor_volume": buy_volume,
            "sell_aggressor_volume": sell_volume,
            "net_delta": delta,
            "delta_percent": delta_percent,
            "cumulative_delta": cvd,
            "cvd_bucket_interval": "1m",
            "cvd_scope": "returned_batch_only",
            "cvd_points": cvd_points,
            "bias": bias,
            "first_trade_time": first_time,
            "last_trade_time": last_time,
            "method_note": (
                "Delta dihitung dari kuantitas Binance aggregated trades: buyer aggressor "
                "ketika buyer bukan maker; seller aggressor ketika buyer adalah maker. "
                "CVD diakumulasi per bucket 1 menit hanya di dalam batch yang dikembalikan "
                "Binance. Ini bukan full-session CVD persisten, DOM, footprint, atau "
                "order-book absorption."
            ),
        }
