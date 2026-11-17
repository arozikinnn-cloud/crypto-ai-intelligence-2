def _direction_from_analysis(item: dict) -> str:
    side = item.get("side")
    if side in {"BUY", "SELL"}:
        return side
    indicators = item.get("indicators") or {}
    price = indicators.get("last_price")
    ma40 = indicators.get("ma40")
    rsi16 = indicators.get("rsi16")
    above = indicators.get("ichimoku_above_cloud") is True
    below = indicators.get("ichimoku_below_cloud") is True
    if (
        isinstance(price, (int, float))
        and isinstance(ma40, (int, float))
        and isinstance(rsi16, (int, float))
    ):
        if price > ma40 and above and 50 < rsi16 < 70:
            return "BUY"
        if price < ma40 and below and 30 < rsi16 < 50:
            return "SELL"
    return "NO TRADE"


def build_intelligence_decision(
    technical_sides: list[str],
    structure: dict,
    order_flow: dict,
    derivatives: dict,
    trade_order_flow: dict | None = None,
    market_context: dict | None = None,
    timeframe_analyses: list[dict] | None = None,
) -> dict:
    supported = {"BUY", "SELL", "NO TRADE"}
    if not technical_sides or any(side not in supported for side in technical_sides):
        raise ValueError("Provide supported technical decisions for H1, M15 and M5.")

    analyses = timeframe_analyses or []
    by_tf = {str(item.get("timeframe", "")).lower(): item for item in analyses}
    if not {"1h", "15m", "5m"}.issubset(by_tf):
        raise ValueError("The strategy requires H1, M15 and M5 analyses.")

    h1 = by_tf["1h"]
    m15 = by_tf["15m"]
    m5 = by_tf["5m"]
    h1_bias = _direction_from_analysis(h1)
    m15_setup = m15.get("side", "NO TRADE")
    m5_trigger = m5.get("side", "NO TRADE")

    agg = trade_order_flow or {}
    flow_buy = (
        order_flow.get("bias") == "BUY_PRESSURE"
        or agg.get("bias") == "BUY_PRESSURE"
    )
    flow_sell = (
        order_flow.get("bias") == "SELL_PRESSURE"
        or agg.get("bias") == "SELL_PRESSURE"
    )
    bullish_event = structure.get("event") in {"bullish_bos", "bullish_choch"}
    bearish_event = structure.get("event") in {"bearish_bos", "bearish_choch"}

    buy_conflict = (
        h1_bias == "SELL" or m15_setup == "SELL" or m5_trigger == "SELL"
        or flow_sell or bearish_event
    )
    sell_conflict = (
        h1_bias == "BUY" or m15_setup == "BUY" or m5_trigger == "BUY"
        or flow_buy or bullish_event
    )
    buy_score = sum((
        h1_bias == "BUY", m15_setup == "BUY", m5_trigger == "BUY",
        flow_buy, bullish_event,
    ))
    sell_score = sum((
        h1_bias == "SELL", m15_setup == "SELL", m5_trigger == "SELL",
        flow_sell, bearish_event,
    ))
    checks = {
        "h1_bullish_bias": h1_bias == "BUY",
        "m15_bullish_setup": m15_setup == "BUY",
        "m5_bullish_trigger": m5_trigger == "BUY",
        "buy_orderflow_confirmation": flow_buy,
        "bullish_structure": bullish_event,
        "h1_bearish_bias": h1_bias == "SELL",
        "m15_bearish_setup": m15_setup == "SELL",
        "m5_bearish_trigger": m5_trigger == "SELL",
        "sell_orderflow_confirmation": flow_sell,
        "bearish_structure": bearish_event,
    }

    if (
        h1_bias == "BUY" and m15_setup == "BUY"
        and (m5_trigger == "BUY" or flow_buy) and not buy_conflict
    ):
        side, score = "BUY", buy_score
        reasons = [
            "H1 memberi bias bullish berdasarkan MA40, RSI16 dan Ichimoku/Kumo.",
            "M15 memberi setup BUY yang terkonfirmasi.",
            (
                "M5 memberi trigger BUY."
                if m5_trigger == "BUY"
                else "Order flow/aggTrades memberi konfirmasi BUY."
            ),
        ]
        if bullish_event:
            reasons.append("Struktur H1 mendukung bullish.")
    elif (
        h1_bias == "SELL" and m15_setup == "SELL"
        and (m5_trigger == "SELL" or flow_sell) and not sell_conflict
    ):
        side, score = "SELL", sell_score
        reasons = [
            "H1 memberi bias bearish berdasarkan MA40, RSI16 dan Ichimoku/Kumo.",
            "M15 memberi setup SELL yang terkonfirmasi.",
            (
                "M5 memberi trigger SELL."
                if m5_trigger == "SELL"
                else "Order flow/aggTrades memberi konfirmasi SELL."
            ),
        ]
        if bearish_event:
            reasons.append("Struktur H1 mendukung bearish.")
    else:
        side, score = "NO TRADE", max(buy_score, sell_score)
        reasons = [
            "NO TRADE: H1 sebagai bias dan M15 sebagai setup wajib searah; "
            "M5 atau order flow/aggTrades harus memberi minimal satu pemicu searah."
        ]
        if buy_conflict or sell_conflict:
            reasons.append("Ada konfirmasi berlawanan yang memblokir entry.")
        if h1_bias == "NO TRADE":
            reasons.append("Bias H1 belum valid dari MA40, RSI16 dan Ichimoku/Kumo.")
        if m15_setup == "NO TRADE":
            reasons.append("Setup M15 belum memenuhi syarat teknikal.")
        if m5_trigger == "NO TRADE" and not flow_buy and not flow_sell:
            reasons.append("Trigger M5 dan tekanan order flow belum tersedia/searah.")

    trade_plan = None
    if side in {"BUY", "SELL"}:
        entry = m15.get("entry")
        stop = m15.get("stop_loss")
        valid = (
            isinstance(entry, (int, float))
            and isinstance(stop, (int, float))
            and entry > 0
            and (
                (side == "BUY" and stop < entry)
                or (side == "SELL" and stop > entry)
            )
        )
        if valid:
            risk = abs(float(entry) - float(stop))
            target = (
                float(entry) + risk * 1.5
                if side == "BUY"
                else float(entry) - risk * 1.5
            )
            trade_plan = {
                "entry": float(entry),
                "stop_loss": float(stop),
                "take_profit": target,
                "risk_reward": 1.5,
                "source_timeframe": "15m",
                "method": "ATR-based M15 stop, fixed 1:1.5 risk/reward.",
            }
        else:
            side = "NO TRADE"
            reasons = ["Sinyal dibatalkan karena level entry/SL M15 tidak valid."]

    context = market_context or {}
    notes = [
        "Strategi utama: H1 menentukan bias, M15 menentukan setup, M5 menjadi trigger. "
        "RSI16, MA40 dan Ichimoku/Kumo digunakan pada setiap timeframe.",
        "H1 dan M15 wajib searah; M5 atau order flow/aggTrades wajib memberi pemicu "
        "searah. Konfirmasi yang berlawanan memblokir entry.",
        "Order flow, OI/funding, CVD dan likuidasi adalah konteks tambahan, "
        "bukan pengganti konfirmasi teknikal.",
    ]
    for section in ("cvd_history", "order_book", "liquidations"):
        note = context.get(section, {}).get("note")
        if note:
            notes.append(note)
    if derivatives.get("source_market") == "unavailable":
        notes.append(
            "Data derivatif tidak tersedia dan tidak digunakan sebagai konfirmasi BUY/SELL."
        )

    return {
        "side": side,
        "confluence_score": score,
        "max_confluence": 5,
        "score_note": (
            "Skor dari lima komponen: bias H1, setup M15, trigger M5, order flow, "
            "dan struktur. Skor bukan probabilitas atau win-rate."
        ),
        "reasons": reasons,
        "context_notes": notes,
        "checks": checks,
        "strategy_mode": "ICHIMOKU_RSI16_MA40_H1_M15_M5",
        "trade_plan": trade_plan,
    }
