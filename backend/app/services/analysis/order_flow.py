from math import isfinite
from app.services.market_data.base import NormalizedCandle


def analyze_order_flow(candles: list[NormalizedCandle], lookback: int = 20) -> dict:
    if not 2 <= lookback <= 100:
        raise ValueError("lookback must be between 2 and 100.")
    if len(candles) < lookback:
        raise ValueError(f"At least {lookback} candles are required.")

    selected = candles[-lookback:]
    symbol = selected[0].symbol
    timeframe = selected[0].timeframe
    previous_time = None
    deltas: list[float] = []
    buy_volumes: list[float] = []
    sell_volumes: list[float] = []

    for candle in selected:
        if candle.symbol != symbol or candle.timeframe != timeframe:
            raise ValueError("Candles must have one consistent symbol and timeframe.")
        if previous_time is not None and candle.open_time <= previous_time:
            raise ValueError("Candles must be in chronological order without duplicates.")
        previous_time = candle.open_time
        if candle.taker_buy_volume is None:
            raise ValueError("Taker-buy volume is unavailable for one or more candles.")
        values = (candle.volume, candle.taker_buy_volume)
        if not all(isfinite(value) for value in values):
            raise ValueError("Order-flow input contains a non-finite value.")
        buy = candle.taker_buy_volume
        sell = candle.volume - buy
        if candle.volume < 0 or buy < 0 or sell < -1e-8:
            raise ValueError("Invalid taker-buy volume in candle data.")
        sell = max(0.0, sell)
        buy_volumes.append(buy)
        sell_volumes.append(sell)
        deltas.append(buy - sell)

    total_volume = sum(buy_volumes) + sum(sell_volumes)
    total_delta = sum(deltas)
    delta_percent = total_delta / total_volume * 100 if total_volume else 0.0
    if delta_percent >= 5:
        bias = "BUY_PRESSURE"
    elif delta_percent <= -5:
        bias = "SELL_PRESSURE"
    else:
        bias = "BALANCED"

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "source_market": "binance_spot_klines",
        "source_market": "binance_spot_klines",
        "lookback": len(selected),
        "buy_volume": sum(buy_volumes),
        "sell_volume": sum(sell_volumes),
        "net_delta": total_delta,
        "delta_percent": delta_percent,
        "cumulative_delta": total_delta,
        "bias": bias,
        "method_note": (
            "Delta/CVD window dihitung per candle dari taker-buy base volume dikurangi "
            "estimasi sell-aggressor volume (total volume - taker buy), lalu dijumlahkan "
            "pada lookback terpilih. Ini proxy dari kline, bukan DOM/footprint atau "
            "riwayat CVD penuh sejak awal sesi."
        ),
    }
