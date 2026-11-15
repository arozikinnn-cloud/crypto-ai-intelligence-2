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


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def atr(candles: list[NormalizedCandle], period: int = 14) -> float | None:
    if len(candles) <= period:
        return None
    true_ranges = []
    for previous, current in zip(candles, candles[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return sum(true_ranges[-period:]) / period


def calculate_indicators(candles: list[NormalizedCandle]) -> dict[str, float | str | None]:
    closes = [item.close for item in candles]
    volumes = [item.volume for item in candles]
    ema20_series = _ema(closes, 20)
    ema50_series = _ema(closes, 50)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    macd_series = [
        fast - slow for fast, slow in zip(ema12[-len(ema26):], ema26)
    ] if ema12 and ema26 else []
    macd_signal_series = _ema(macd_series, 9) if len(macd_series) >= 9 else []
    volume_baseline = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else None
    latest_volume_ratio = (
        volumes[-1] / volume_baseline
        if volume_baseline and volume_baseline > 0 else None
    )
    market_structure = "insufficient_history"
    if len(candles) >= 40:
        previous_window = candles[-40:-20]
        recent_window = candles[-20:]
        higher_high = max(item.high for item in recent_window) > max(
            item.high for item in previous_window
        )
        higher_low = min(item.low for item in recent_window) > min(
            item.low for item in previous_window
        )
        lower_high = max(item.high for item in recent_window) < max(
            item.high for item in previous_window
        )
        lower_low = min(item.low for item in recent_window) < min(
            item.low for item in previous_window
        )
        if higher_high and higher_low:
            market_structure = "higher_high_higher_low"
        elif lower_high and lower_low:
            market_structure = "lower_high_lower_low"
        else:
            market_structure = "mixed_or_range"

    return {
        "market_structure": market_structure,
        "last_price": closes[-1] if closes else None,
        "ema20": ema20_series[-1] if ema20_series else None,
        "ema50": ema50_series[-1] if ema50_series else None,
        "rsi14": rsi(closes, 14),
        "macd": macd_series[-1] if macd_series else None,
        "macd_signal": macd_signal_series[-1] if macd_signal_series else None,
        "atr14": atr(candles, 14),
        "volume_ratio": latest_volume_ratio,
        "support_20": min(item.low for item in candles[-20:]) if len(candles) >= 20 else None,
        "resistance_20": max(item.high for item in candles[-20:]) if len(candles) >= 20 else None,
    }


def validate_analysis_input(candles: list[NormalizedCandle]) -> None:
    if len(candles) < 60:
        raise ValueError("At least 60 candles are required for stable indicator calculations.")
    for candle in candles:
        values = (
            candle.open, candle.high, candle.low, candle.close,
            candle.volume, candle.quote_volume,
        )
        if not all(isfinite(value) for value in values):
            raise ValueError("Candle data contains a non-finite value.")
