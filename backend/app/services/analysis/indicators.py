from math import isfinite
from app.services.market_data.base import NormalizedCandle


def _ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    multiplier = 2 / (period + 1)
    result = [sum(values[:period]) / period]
    for value in values[period:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def rsi(values: list[float], period: int = 16) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def _midpoint(candles: list[NormalizedCandle], end: int, period: int) -> float | None:
    start = end - period + 1
    if start < 0:
        return None
    window = candles[start:end + 1]
    return (max(c.high for c in window) + min(c.low for c in window)) / 2


def atr(candles: list[NormalizedCandle], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    ranges = [
        max(c.high-c.low, abs(c.high-p.close), abs(c.low-p.close))
        for p, c in zip(candles, candles[1:])
    ]
    return sum(ranges[-period:]) / period


def calculate_indicators(candles: list[NormalizedCandle]) -> dict:
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    last = len(candles) - 1
    ma40 = sum(closes[-40:]) / 40 if len(closes) >= 40 else None
    ma40_previous = sum(closes[-41:-1]) / 40 if len(closes) >= 41 else None
    tenkan = _midpoint(candles, last, 9)
    kijun = _midpoint(candles, last, 26)
    # Current plotted Kumo is formed by values calculated 26 candles earlier.
    cloud_index = last - 26
    span_a = None
    span_b = None
    if cloud_index >= 51:
        old_tenkan = _midpoint(candles, cloud_index, 9)
        old_kijun = _midpoint(candles, cloud_index, 26)
        span_b = _midpoint(candles, cloud_index, 52)
        if old_tenkan is not None and old_kijun is not None:
            span_a = (old_tenkan + old_kijun) / 2
    cloud_top = max(span_a, span_b) if span_a is not None and span_b is not None else None
    cloud_bottom = min(span_a, span_b) if span_a is not None and span_b is not None else None
    previous_cloud_index = last - 27
    previous_span_a = previous_span_b = None
    if previous_cloud_index >= 51:
        prev_tenkan = _midpoint(candles, previous_cloud_index, 9)
        prev_kijun = _midpoint(candles, previous_cloud_index, 26)
        previous_span_b = _midpoint(candles, previous_cloud_index, 52)
        if prev_tenkan is not None and prev_kijun is not None:
            previous_span_a = (prev_tenkan + prev_kijun) / 2
    previous_cloud_top = (
        max(previous_span_a, previous_span_b)
        if previous_span_a is not None and previous_span_b is not None else None
    )
    previous_cloud_bottom = (
        min(previous_span_a, previous_span_b)
        if previous_span_a is not None and previous_span_b is not None else None
    )
    price = closes[-1]
    previous_close = closes[-2]
    above_cloud = cloud_top is not None and price > cloud_top
    below_cloud = cloud_bottom is not None and price < cloud_bottom
    bullish_breakout = (
        above_cloud and previous_cloud_top is not None
        and previous_close <= previous_cloud_top
    )
    bearish_breakout = (
        below_cloud and previous_cloud_bottom is not None
        and previous_close >= previous_cloud_bottom
    )
    bullish_retest = (
        cloud_top is not None and candles[-1].low <= cloud_top
        and price > cloud_top and price >= candles[-1].open
    )
    bearish_retest = (
        cloud_bottom is not None and candles[-1].high >= cloud_bottom
        and price < cloud_bottom and price <= candles[-1].open
    )
    volume_base = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None
    ema20_values = _ema(closes, 20)
    ema50_values = _ema(closes, 50)
    ema12_values = _ema(closes, 12)
    ema26_values = _ema(closes, 26)
    macd_values = []
    if ema12_values and ema26_values:
        macd_values = [
            fast - slow
            for fast, slow in zip(ema12_values[-len(ema26_values):], ema26_values)
        ]
    macd_signal_values = _ema(macd_values, 9) if len(macd_values) >= 9 else []
    return {
        "market_structure": (
            "bullish" if ma40 is not None and price > ma40
            else "bearish" if ma40 is not None and price < ma40
            else "unavailable"
        ),
        "last_price": price,
        "ma40": ma40,
        "ma40_previous": ma40_previous,
        "ma40_bullish_rejection": bool(
            ma40 is not None and candles[-1].low <= ma40
            and price > ma40 and candles[-1].close >= candles[-1].open
        ),
        "ma40_bearish_rejection": bool(
            ma40 is not None and candles[-1].high >= ma40
            and price < ma40 and candles[-1].close <= candles[-1].open
        ),
        "ma40_bullish_breakout": bool(
            ma40 is not None and ma40_previous is not None
            and previous_close <= ma40_previous and price > ma40
        ),
        "ma40_bearish_breakout": bool(
            ma40 is not None and ma40_previous is not None
            and previous_close >= ma40_previous and price < ma40
        ),
        "ema20": ema20_values[-1] if ema20_values else None,
        "ema50": ema50_values[-1] if ema50_values else None,
        "rsi16": rsi(closes, 16),
        "rsi14": rsi(closes, 14),
        "macd": macd_values[-1] if macd_values else None,
        "macd_signal": macd_signal_values[-1] if macd_signal_values else None,
        "atr14": atr(candles, 14),
        "volume_ratio": volumes[-1] / volume_base if volume_base and volume_base > 0 else None,
        "support_20": min(c.low for c in candles[-20:]) if len(candles) >= 20 else None,
        "resistance_20": max(c.high for c in candles[-20:]) if len(candles) >= 20 else None,
        "ichimoku_tenkan": tenkan,
        "ichimoku_kijun": kijun,
        "ichimoku_senkou_a": span_a,
        "ichimoku_senkou_b": span_b,
        "ichimoku_cloud_top": cloud_top,
        "ichimoku_cloud_bottom": cloud_bottom,
        "ichimoku_above_cloud": above_cloud,
        "ichimoku_below_cloud": below_cloud,
        "ichimoku_bullish_breakout": bullish_breakout,
        "ichimoku_bearish_breakout": bearish_breakout,
        "ichimoku_bullish_retest": bullish_retest,
        "ichimoku_bearish_retest": bearish_retest,
    }


def validate_analysis_input(candles: list[NormalizedCandle]) -> None:
    if len(candles) < 80:
        raise ValueError(
            "At least 80 closed candles are required for RSI16, MA40 and Ichimoku calculations."
        )
    for candle in candles:
        values = (
            candle.open, candle.high, candle.low, candle.close,
            candle.volume, candle.quote_volume,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("Candle data contains a non-finite value.")
