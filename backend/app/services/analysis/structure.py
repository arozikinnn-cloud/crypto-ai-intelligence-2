from app.services.market_data.base import NormalizedCandle


def _latest_order_block(
    candles: list[NormalizedCandle], bullish_break: bool
) -> dict | None:
    for candle in reversed(candles[-21:-1]):
        is_opposite = candle.close < candle.open if bullish_break else candle.close > candle.open
        if is_opposite:
            return {
                "low": candle.low,
                "high": candle.high,
                "formed_at": candle.open_time,
            }
    return None


def analyze_structure(candles: list[NormalizedCandle], pivot_span: int = 2) -> dict:
    if pivot_span < 1 or pivot_span > 5:
        raise ValueError("pivot_span must be between 1 and 5.")
    if len(candles) < max(20, pivot_span * 2 + 5):
        raise ValueError("At least 20 candles are required for structure analysis.")

    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    for index in range(pivot_span, len(candles) - pivot_span):
        window = candles[index - pivot_span:index + pivot_span + 1]
        high = candles[index].high
        low = candles[index].low
        unique_high = sum(item.high == high for item in window) == 1
        unique_low = sum(item.low == low for item in window) == 1
        if high == max(item.high for item in window) and unique_high:
            highs.append((index, high))
        if low == min(item.low for item in window) and unique_low:
            lows.append((index, low))

    last = candles[-1]
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
    if last_high is not None and last.close > last_high:
        event = "bullish_bos" if trend == "bullish" else "bullish_choch"
    elif last_low is not None and last.close < last_low:
        event = "bearish_bos" if trend == "bearish" else "bearish_choch"

    swept_high = last_high is not None and last.high > last_high and last.close < last_high
    swept_low = last_low is not None and last.low < last_low and last.close > last_low
    if swept_high and swept_low:
        liquidity_sweep = "both_sides_swept"
    elif swept_high:
        liquidity_sweep = "bearish_sweep"
    elif swept_low:
        liquidity_sweep = "bullish_sweep"
    else:
        liquidity_sweep = "none"

    bullish_fvg = None
    bearish_fvg = None
    for index in range(max(2, len(candles) - 50), len(candles)):
        first = candles[index - 2]
        third = candles[index]
        later = candles[index + 1:]
        if third.low > first.high:
            zone_low, zone_high = first.high, third.low
            mitigated = any(item.low <= zone_high for item in later)
            fully_mitigated = any(item.low <= zone_low for item in later)
            bullish_fvg = {
                "low": zone_low,
                "high": zone_high,
                "formed_at": third.open_time,
                "mitigated": mitigated,
                "fully_mitigated": fully_mitigated,
            }
        if third.high < first.low:
            zone_low, zone_high = third.high, first.low
            mitigated = any(item.high >= zone_low for item in later)
            fully_mitigated = any(item.high >= zone_high for item in later)
            bearish_fvg = {
                "low": zone_low,
                "high": zone_high,
                "formed_at": third.open_time,
                "mitigated": mitigated,
                "fully_mitigated": fully_mitigated,
            }

    bullish_order_block = (
        _latest_order_block(candles, True) if event.startswith("bullish_") else None
    )
    bearish_order_block = (
        _latest_order_block(candles, False) if event.startswith("bearish_") else None
    )

    return {
        "trend": trend,
        "event": event,
        "liquidity_sweep": liquidity_sweep,
        "last_swing_high": last_high,
        "last_swing_low": last_low,
        "bullish_fvg": bullish_fvg,
        "bearish_fvg": bearish_fvg,
        "bullish_order_block": bullish_order_block,
        "bearish_order_block": bearish_order_block,
        "pivot_count": len(highs) + len(lows),
        "method_note": (
            "Pivot dikonfirmasi dengan candle kanan. Sweep berarti wick melewati swing "
            "lalu close kembali ke dalam. Order block adalah candle lawan terakhir "
            "sebelum break, zona full candle. FVG memakai gap tiga-candle; mitigasi "
            "diukur dari candle setelah formasi. Semua adalah heuristik, bukan order flow."
        ),
    }
