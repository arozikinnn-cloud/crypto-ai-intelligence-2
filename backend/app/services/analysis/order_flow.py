from app.services.market_data.base import NormalizedCandle


def analyze_order_flow(candles: list[NormalizedCandle], lookback: int = 20) -> dict:
    if lookback < 2 or lookback > 100:
        raise ValueError("lookback must be between 2 and 100.")
    selected = candles[-lookback:]
    if len(selected) < 2:
        raise ValueError("At least 2 candles are required for order-flow analysis.")
    if any(item.taker_buy_volume is None for item in selected):
        raise ValueError("Taker-buy volume is unavailable for one or more candles.")

    deltas = []
    for candle in selected:
        buy = float(candle.taker_buy_volume)
        sell = candle.volume - buy
        if buy < 0 or sell < -1e-8:
            raise ValueError("Invalid taker-buy volume in candle data.")
        sell = max(0.0, sell)
        deltas.append(buy - sell)

    total_delta = sum(deltas)
    total_volume = sum(item.volume for item in selected)
    buy_volume = sum(float(item.taker_buy_volume) for item in selected)
    sell_volume = total_volume - buy_volume
    delta_percent = (total_delta / total_volume * 100) if total_volume else 0.0
    if delta_percent >= 5:
        bias = "BUY_PRESSURE"
    elif delta_percent <= -5:
        bias = "SELL_PRESSURE"
    else:
        bias = "BALANCED"

    return {
        "lookback": len(selected),
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "net_delta": total_delta,
        "delta_percent": delta_percent,
        "cumulative_delta": total_delta,
        "bias": bias,
        "method_note": (
            "Delta dihitung dari taker-buy base volume dikurangi estimasi sell "
            "agresif (total volume - taker buy); bukan data DOM atau footprint."
        ),
    }
