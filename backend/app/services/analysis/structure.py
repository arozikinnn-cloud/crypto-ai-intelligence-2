from app.services.market_data.base import NormalizedCandle


def analyze_structure(candles: list[NormalizedCandle], pivot_span: int = 2) -> dict:
    if len(candles) < max(20, pivot_span * 2 + 5):
        raise ValueError("At least 20 candles are required for structure analysis.")
    if pivot_span < 1 or pivot_span > 5:
        raise ValueError("pivot_span must be between 1 and 5.")

    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index in range(pivot_span, len(candles) - pivot_span):
        window = candles[index - pivot_span:index + pivot_span + 1]
        high = candles[index].high
        low = candles[index].low
        is_unique_high = sum(item.high == high for item in window) == 1
        if high == max(item.high for item in window) and is_unique_high:
            highs.append((index, high))
        is_unique_low = sum(item.low == low for item in window) == 1
        if low == min(item.low for item in window) and is_unique_low:
            lows.append((index, low))

    last_close = candles[-1].close
    recent_highs = highs[-2:]
    recent_lows = lows[-2:]
    trend = "range_or_unconfirmed"
    if len(recent_highs) == 2 and len(recent_lows) == 2:
        higher_high = recent_highs[-1][1] > recent_highs[-2][1]
        higher_low = recent_lows[-1][1] > recent_lows[-2][1]
        lower_high = recent_highs[-1][1] < recent_highs[-2][1]
        lower_low = recent_lows[-1][1] < recent_lows[-2][1]
        if higher_high and higher_low:
            trend = "bullish"
        elif lower_high and lower_low:
            trend = "bearish"

    last_high = recent_highs[-1][1] if recent_highs else None
    last_low = recent_lows[-1][1] if recent_lows else None
    event = "none"
    if last_high is not None and last_close > last_high:
        event = "bullish_bos" if trend == "bullish" else "bullish_choch"
    elif last_low is not None and last_close < last_low:
        event = "bearish_bos" if trend == "bearish" else "bearish_choch"

    bullish_fvg = None
    bearish_fvg = None
    for index in range(max(2, len(candles) - 50), len(candles)):
        first = candles[index - 2]
        third = candles[index]
        if third.low > first.high:
            bullish_fvg = {"low": first.high, "high": third.low, "formed_at": third.open_time}
        if third.high < first.low:
            bearish_fvg = {"low": third.high, "high": first.low, "formed_at": third.open_time}

    return {
        "trend": trend,
        "event": event,
        "last_swing_high": last_high,
        "last_swing_low": last_low,
        "bullish_fvg": bullish_fvg,
        "bearish_fvg": bearish_fvg,
        "pivot_count": len(highs) + len(lows),
        "method_note": (
            "Pivot memakai 2 candle kiri/kanan; BOS/CHOCH dikonfirmasi saat candle "
            "terakhir ditutup melewati swing. FVG adalah gap tiga-candle sederhana."
        ),
    }
