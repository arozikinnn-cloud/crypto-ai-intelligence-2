from app.services.market_data.base import MarketDataError, NormalizedCandle


def validate_candles(candles: list[NormalizedCandle]) -> None:
    previous_open_time = None
    for candle in candles:
        values = (candle.open, candle.high, candle.low, candle.close, candle.volume, candle.quote_volume)
        if any(value < 0 for value in values):
            raise MarketDataError("Exchange returned a negative market value.")
        if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close):
            raise MarketDataError("Candle OHLC values are inconsistent.")
        if candle.low > candle.high:
            raise MarketDataError("Candle low exceeds candle high.")
        if candle.trades < 0 or candle.close_time < candle.open_time:
            raise MarketDataError("Candle metadata is inconsistent.")
        if previous_open_time is not None and candle.open_time <= previous_open_time:
            raise MarketDataError("Candles are duplicated or not chronologically ordered.")
        previous_open_time = candle.open_time
