def build_intelligence_decision(
    technical_sides: list[str],
    structure: dict,
    order_flow: dict,
    derivatives: dict,
    trade_order_flow: dict | None = None,
    market_context: dict | None = None,
    timeframe_analyses: list[dict] | None = None,
) -> dict:
    if not technical_sides or any(
        side not in {"BUY", "SELL", "NO TRADE"} for side in technical_sides
    ):
        raise ValueError("Provide supported technical decisions for 15m and 30m.")

    analyses = timeframe_analyses or []
    by_tf = {
        str(item.get("timeframe", "")).lower(): item
        for item in analyses
    }
    m15 = by_tf.get("15m", {})
    m30 = by_tf.get("30m", {})
    m15_side = m15.get("side")
    m30_side = m30.get("side")

    flow_buy = (
        order_flow.get("bias") == "BUY_PRESSURE"
        or (trade_order_flow or {}).get("bias") == "BUY_PRESSURE"
    )
    flow_sell = (
        order_flow.get("bias") == "SELL_PRESSURE"
        or (trade_order_flow or {}).get("bias") == "SELL_PRESSURE"
    )
    m30_ind = m30.get("indicators", {})
    m15_buy = m15_side == "BUY"
    m15_sell = m15_side == "SELL"
    m30_buy = m30_side == "BUY" or (
        m30_ind.get("last_price") is not None
        and m30_ind.get("ma40") is not None
        and m30_ind["last_price"] > m30_ind["ma40"]
        and m30_ind.get("ichimoku_above_cloud") is True
    )
    m30_sell = m30_side == "SELL" or (
        m30_ind.get("last_price") is not None
        and m30_ind.get("ma40") is not None
        and m30_ind["last_price"] < m30_ind["ma40"]
        and m30_ind.get("ichimoku_below_cloud") is True
    )
    bullish_event = structure.get("event") in {
        "bullish_bos",
        "bullish_choch",
    }
    bearish_event = structure.get("event") in {
        "bearish_bos",
        "bearish_choch",
    }
    buy_conflict = m15_sell or m30_sell or flow_sell or bearish_event
    sell_conflict = m15_buy or m30_buy or flow_buy or bullish_event
    buy_score = sum((m30_buy, m15_buy, flow_buy, bullish_event))
    sell_score = sum((m30_sell, m15_sell, flow_sell, bearish_event))
    checks = {
        "m30_bullish_bias": bool(m30_buy),
        "m15_bullish_setup": bool(m15_buy),
        "buy_orderflow_confirmation": bool(flow_buy),
        "bullish_structure": bool(bullish_event),
        "m30_bearish_bias": bool(m30_sell),
        "m15_bearish_setup": bool(m15_sell),
        "sell_orderflow_confirmation": bool(flow_sell),
        "bearish_structure": bool(bearish_event),
    }

    if m30_buy and m15_buy and not buy_conflict:
        side, score = "BUY", buy_score
        reasons = [
            "Bias M30 bullish berdasarkan MA40 dan Ichimoku.",
            "Setup M15 BUY terkonfirmasi oleh MA40, RSI16, dan Ichimoku/Kumo.",
        ]
        if flow_buy:
            reasons.append("Order flow/aggTrades mendukung tekanan beli.")
        if bullish_event:
            reasons.append("Struktur market mendukung bullish.")
    elif m30_sell and m15_sell and not sell_conflict:
        side, score = "SELL", sell_score
        reasons = [
            "Bias M30 bearish berdasarkan MA40 dan Ichimoku.",
            "Setup M15 SELL terkonfirmasi oleh MA40, RSI16, dan Ichimoku/Kumo.",
        ]
        if flow_sell:
            reasons.append("Order flow/aggTrades mendukung tekanan jual.")
        if bearish_event:
            reasons.append("Struktur market mendukung bearish.")
    else:
        side, score = "NO TRADE", max(buy_score, sell_score)
        reasons = [
            "NO TRADE: M30 sebagai arah utama dan M15 sebagai pemicu belum "
            "searah, atau ada konfirmasi berlawanan."
        ]

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
            reasons = [
                "Sinyal dibatalkan karena level entry/SL M15 tidak valid."
            ]

    context = market_context or {}
    notes = [
        "Strategi utama: M30 menentukan bias; M15 menentukan setup; "
        "RSI 16, MA40 dan Ichimoku/Kumo wajib diperiksa.",
        "Order flow, OI/funding, CVD dan likuidasi adalah konteks tambahan, "
        "bukan pengganti konfirmasi teknikal.",
    ]
    for section in ("cvd_history", "order_book", "liquidations"):
        note = context.get(section, {}).get("note")
        if note:
            notes.append(note)
    if derivatives.get("source_market") == "unavailable":
        notes.append(
            "Data derivatif tidak tersedia dan tidak digunakan sebagai konfirmasi."
        )

    return {
        "side": side,
        "confluence_score": score,
        "max_confluence": 4,
        "score_note": (
            "Empat komponen konfluensi M30, M15, order flow, dan struktur; "
            "bukan probabilitas atau jaminan win-rate."
        ),
        "reasons": reasons,
        "context_notes": notes,
        "checks": checks,
        "strategy_mode": "ICHIMOKU_RSI16_MA40_M15_M30",
        "trade_plan": trade_plan,
    }
