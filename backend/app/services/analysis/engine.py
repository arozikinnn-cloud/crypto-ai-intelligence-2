from datetime import datetime, timezone
from app.services.market_data.base import NormalizedCandle
from app.services.analysis.indicators import calculate_indicators, validate_analysis_input


def analyze_market(candles: list[NormalizedCandle], risk_reward: float = 1.5, atr_multiplier: float = 1.5) -> dict:
    validate_analysis_input(candles)
    if risk_reward <= 0 or atr_multiplier <= 0:
        raise ValueError("Risk parameters must be greater than zero.")
    values = calculate_indicators(candles)
    price = float(values["last_price"])
    ma40, rsi16, atr14 = values["ma40"], values["rsi16"], values["atr14"]
    tenkan, kijun = values["ichimoku_tenkan"], values["ichimoku_kijun"]
    ready = all(v is not None for v in (ma40, rsi16, atr14, tenkan, kijun,
                                        values["ichimoku_cloud_top"], values["ichimoku_cloud_bottom"]))
    buy_checks = {
        "price_above_ma40": ma40 is not None and price > ma40,
        "ichimoku_bullish": tenkan is not None and kijun is not None and tenkan > kijun,
        "rsi16_bullish": rsi16 is not None and 50 < rsi16 < 70,
        "above_or_breaking_kumo": bool(values["ichimoku_above_cloud"] or values["ichimoku_bullish_breakout"]),
    }
    sell_checks = {
        "price_below_ma40": ma40 is not None and price < ma40,
        "ichimoku_bearish": tenkan is not None and kijun is not None and tenkan < kijun,
        "rsi16_bearish": rsi16 is not None and 30 < rsi16 < 50,
        "below_or_breaking_kumo": bool(values["ichimoku_below_cloud"] or values["ichimoku_bearish_breakout"]),
    }
    buy_score, sell_score = sum(buy_checks.values()), sum(sell_checks.values())
    if ready and buy_score >= 3 and buy_checks["price_above_ma40"] and buy_checks["above_or_breaking_kumo"]:
        side, score = "BUY", buy_score
        stop_loss = price - float(atr14) * atr_multiplier
        reasons = ["Harga di atas MA40 (bias bullish)."]
        if buy_checks["ichimoku_bullish"]: reasons.append("Tenkan-sen berada di atas Kijun-sen.")
        reasons.append(f"RSI 16 = {float(rsi16):.2f}, mendukung momentum bullish.")
        if values["ichimoku_bullish_breakout"]:
            reasons.append("Candle close menembus Kumo ke atas (bullish breakout).")
        elif values["ichimoku_bullish_retest"]:
            reasons.append("Harga melakukan retest/rejection bullish pada batas Kumo.")
        else:
            reasons.append("Harga bertahan di atas Kumo.")
    elif ready and sell_score >= 3 and sell_checks["price_below_ma40"] and sell_checks["below_or_breaking_kumo"]:
        side, score = "SELL", sell_score
        stop_loss = price + float(atr14) * atr_multiplier
        reasons = ["Harga di bawah MA40 (bias bearish)."]
        if sell_checks["ichimoku_bearish"]: reasons.append("Tenkan-sen berada di bawah Kijun-sen.")
        reasons.append(f"RSI 16 = {float(rsi16):.2f}, mendukung momentum bearish.")
        if values["ichimoku_bearish_breakout"]:
            reasons.append("Candle close menembus Kumo ke bawah (bearish breakout).")
        elif values["ichimoku_bearish_retest"]:
            reasons.append("Harga melakukan retest/rejection bearish pada batas Kumo.")
        else:
            reasons.append("Harga bertahan di bawah Kumo.")
    else:
        side, score, stop_loss = "NO TRADE", max(buy_score, sell_score), None
        reasons = ["Konfirmasi MA40, Ichimoku/Kumo, dan RSI16 belum selaras; tunggu setup yang lebih jelas."]
        if values["ichimoku_bullish_breakout"] or values["ichimoku_bearish_breakout"]:
            reasons.append("Breakout Kumo terdeteksi, tetapi konfirmasi tren/momentum lain belum cukup.")
    take_profit = None
    if stop_loss is not None:
        risk = abs(price - stop_loss)
        take_profit = price + risk * risk_reward if side == "BUY" else price - risk * risk_reward
    return {
        "symbol": candles[-1].symbol, "timeframe": candles[-1].timeframe,
        "timestamp": datetime.now(timezone.utc), "side": side,
        "entry": price if side != "NO TRADE" else None,
        "stop_loss": stop_loss, "take_profit": take_profit,
        "risk_reward": risk_reward if side != "NO TRADE" else None,
        "confluence_score": score, "max_confluence": 4,
        "score_note": "Skor konfluensi MA40, Ichimoku, RSI16 dan posisi terhadap Kumo; bukan probabilitas win-rate.",
        "indicators": values, "reasons": reasons, "candle_count": len(candles),
    }
