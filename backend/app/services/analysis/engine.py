from datetime import datetime, timezone
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.indicators import calculate_indicators, validate_analysis_input


def analyze_market(
    candles: list[NormalizedCandle],
    risk_reward: float = 1.5,
    atr_multiplier: float = 1.5,
) -> dict:
    validate_analysis_input(candles)
    if risk_reward <= 0 or atr_multiplier <= 0:
        raise ValueError("Risk parameters must be greater than zero.")

    values = calculate_indicators(candles)
    price = float(values["last_price"])
    ema20 = values["ema20"]
    ema50 = values["ema50"]
    rsi14 = values["rsi14"]
    macd = values["macd"]
    macd_signal = values["macd_signal"]
    atr14 = values["atr14"]

    bullish_checks = [
        ema20 is not None and ema50 is not None and price > ema20 > ema50,
        rsi14 is not None and 50 <= rsi14 < 75,
        macd is not None and macd_signal is not None and macd > macd_signal,
        values["volume_ratio"] is not None and values["volume_ratio"] >= 1.0,
    ]
    bearish_checks = [
        ema20 is not None and ema50 is not None and price < ema20 < ema50,
        rsi14 is not None and 25 < rsi14 <= 50,
        macd is not None and macd_signal is not None and macd < macd_signal,
        values["volume_ratio"] is not None and values["volume_ratio"] >= 1.0,
    ]

    atr_is_valid = atr14 is not None and float(atr14) > 0\n\n    if atr_is_valid and sum(bullish_checks) >= 3 and sum(bullish_checks) > sum(bearish_checks):
        side = "BUY"
        stop_loss = price - float(atr14) * atr_multiplier if atr14 else None
        take_profit = price + (price - stop_loss) * risk_reward if stop_loss is not None else None
        reasons = [
            label for check, label in zip(bullish_checks, [
                "Harga berada di atas EMA20 dan EMA50 dengan susunan bullish.",
                "RSI berada di zona momentum bullish, belum overbought.",
                "MACD berada di atas garis sinyal.",
                "Volume terkini setidaknya setara rata-rata 20 candle sebelumnya.",
            ]) if check
        ]
        score = sum(bullish_checks)
    elif atr_is_valid and sum(bearish_checks) >= 3 and sum(bearish_checks) > sum(bullish_checks):
        side = "SELL"
        stop_loss = price + float(atr14) * atr_multiplier if atr14 else None
        take_profit = price - (stop_loss - price) * risk_reward if stop_loss is not None else None
        reasons = [
            label for check, label in zip(bearish_checks, [
                "Harga berada di bawah EMA20 dan EMA50 dengan susunan bearish.",
                "RSI berada di zona momentum bearish.",
                "MACD berada di bawah garis sinyal.",
                "Volume terkini setidaknya setara rata-rata 20 candle sebelumnya.",
            ]) if check
        ]
        score = sum(bearish_checks)
    else:
        side = "NO TRADE"
        stop_loss = None
        take_profit = None
        score = max(sum(bullish_checks), sum(bearish_checks))
        reasons = [
            "Konfirmasi indikator belum cukup selaras; sistem memilih tidak memaksakan entry."
        ]

    return {
        "symbol": candles[-1].symbol,
        "timeframe": candles[-1].timeframe,
        "timestamp": datetime.now(timezone.utc),
        "side": side,
        "entry": price if side != "NO TRADE" else None,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward": risk_reward if side != "NO TRADE" else None,
        "confluence_score": score,
        "max_confluence": 4,
        "score_note": "Skor konfluensi aturan, bukan probabilitas atau win-rate.",
        "indicators": values,
        "reasons": reasons,
        "candle_count": len(candles),
    }
