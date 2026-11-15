import math
from app.services.market_data.base import MarketDataError, NormalizedCandle


def validate_candles(candles: list[NormalizedCandle]) -> None:
    previous_open_time = None
    for candle in candles:
        values = (
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
            candle.quote_volume,
        )
        if not all(math.isfinite(value) for value in values):
            raise MarketDataError("Candle contains a non-finite numeric value.")
        if any(value < 0 for value in values):
            raise MarketDataError("Exchange returned a negative market value.")
        if candle.taker_buy_volume is not None:
            if not math.isfinite(candle.taker_buy_volume):
                raise MarketDataError("Taker-buy volume is not finite.")
            if candle.taker_buy_volume < 0 or candle.taker_buy_volume > candle.volume:
                raise MarketDataError("taker-buy volume is outside total candle volume.")
        if (
            candle.low > min(candle.open, candle.close)
            or candle.high < max(candle.open, candle.close)
        ):
            raise MarketDataError("Candle OHLC values are inconsistent.")
        if candle.low > candle.high:
            raise MarketDataError("Candle low exceeds candle high.")
        if candle.trades < 0 or candle.close_time < candle.open_time:
            raise MarketDataError("Candle metadata is inconsistent.")
        if previous_open_time is not None and candle.open_time <= previous_open_time:
            raise MarketDataError("Candles are duplicated or not chronologically ordered.")
        previous_open_time = candle.open_time



def validate_candle_continuity(candles: list[NormalizedCandle]) -> None:
    """Reject gaps in fixed-duration candle series used for historical simulation."""
    if len(candles) < 2:
        return
    interval = candles[0].timeframe
    if interval.endswith("M"):
        return
    unit = interval[-1]
    try:
        amount = int(interval[:-1])
    except (TypeError, ValueError) as exc:
        raise MarketDataError("Unsupported candle timeframe for continuity check.") from exc
    durations = {
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
        "w": 604_800_000,
    }
    if unit not in durations or amount <= 0:
        raise MarketDataError("Unsupported candle timeframe for continuity check.")
    expected_ms = amount * durations[unit]
    for previous, current in zip(candles, candles[1:]):
        actual_ms = (current.open_time - previous.open_time).total_seconds() * 1000
        if actual_ms != expected_ms:
            raise MarketDataError(
                "Candle series contains a missing, duplicated, or irregular interval."
            )
