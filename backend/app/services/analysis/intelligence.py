def build_intelligence_decision(
    technical_sides: list[str],
    structure: dict,
    order_flow: dict,
    derivatives: dict,
    trade_order_flow: dict | None = None,
    market_context: dict | None = None,
    timeframe_analyses: list[dict] | None = None,
) -> dict:
    if not technical_sides:
        raise ValueError("At least one technical timeframe is required.")
    if any(side not in {"BUY", "SELL", "NO TRADE"} for side in technical_sides):
        raise ValueError("Technical timeframe contains an unsupported decision.")

    analyses = timeframe_analyses or []
    by_tf = {str(item.get("timeframe", "")).lower(): item for item in analyses}
    h1 = by_tf.get("1h", {})
    m15 = by_tf.get("15m", {})
    m5 = by_tf.get("5m", {})
    h1_side, setup_side, m5_side = h1.get("side"), m15.get("side"), m5.get("side")

    # Day-trading hierarchy: H1 establishes bias, M15 supplies the setup,
    # and M5 plus order-flow/aggTrades confirm execution.
    htf_buy = h1_side == "BUY"
    htf_sell = h1_side == "SELL"
    flow_buy = order_flow.get("bias") == "BUY_PRESSURE"
    flow_sell = order_flow.get("bias") == "SELL_PRESSURE"
    tape_buy = (trade_order_flow or {}).get("bias") == "BUY_PRESSURE"
    tape_sell = (trade_order_flow or {}).get("bias") == "SELL_PRESSURE"
    buy_trigger = (flow_buy or tape_buy) and not (flow_sell or tape_sell)
    sell_trigger = (flow_sell or tape_sell) and not (flow_buy or tape_buy)

    bullish_structure = (
        structure.get("event") in {"bullish_bos", "bullish_choch"}
        or structure.get("trend") == "bullish"
    )
    bearish_structure = (
        structure.get("event") in {"bearish_bos", "bearish_choch"}
        or structure.get("trend") == "bearish"
    )
    bullish_checks = {
        "h1_bullish_bias": h1_side == "BUY",
        "m15_buy_setup": setup_side == "BUY",
        "m5_buy_confirmation": m5_side == "BUY",
        "m5_or_tape_buy_confirmation": buy_trigger,
        "bullish_market_structure": bullish_structure,
    }
    bearish_checks = {
        "h1_bearish_bias": h1_side == "SELL",
        "m15_sell_setup": setup_side == "SELL",
        "m5_sell_confirmation": m5_side == "SELL",
        "m5_or_tape_sell_confirmation": sell_trigger,
        "bearish_market_structure": bearish_structure,
    }

    # Five-point confluence: H1 bias, M15 setup, M5 confirmation,
    # order-flow/tape confirmation, and market structure.
    # H1 + M15 alignment are mandatory. Execution can be confirmed by M5
    # OR by a directional order-flow/tape reading; structure is supporting
    # evidence rather than a hard gate. Any clear opposite execution signal
    # blocks the trade.
    buy_execution_conflict = (
        m5_side == "SELL" or flow_sell or tape_sell
        or structure.get("event") in {"bearish_bos", "bearish_choch"}
    )
    sell_execution_conflict = (
        m5_side == "BUY" or flow_buy or tape_buy
        or structure.get("event") in {"bullish_bos", "bullish_choch"}
    )
    buy_execution_confirmed = m5_side == "BUY" or buy_trigger
    sell_execution_confirmed = m5_side == "SELL" or sell_trigger

    bullish_score = sum(bullish_checks.values())
    bearish_score = sum(bearish_checks.values())

    if (
        htf_buy
        and setup_side == "BUY"
        and buy_execution_confirmed
        and not buy_execution_conflict
        and bullish_score >= 3
    ):
        side = "BUY"
        score = bullish_score
        reasons = [
            "Bias H1 bullish.",
            "M15 membentuk setup BUY berdasarkan indikator teknikal.",
            (
                "Konfirmasi entry BUY tersedia dari M5."
                if m5_side == "BUY"
                else "Konfirmasi entry BUY tersedia dari order flow/aggTrades."
            ),
            f"Skor konfluensi BUY {score}/5 (minimum 3/5).",
        ]
        if bullish_structure:
            reasons.append("Struktur market mendukung skenario bullish.")
    elif (
        htf_sell
        and setup_side == "SELL"
        and sell_execution_confirmed
        and not sell_execution_conflict
        and bearish_score >= 3
    ):
        side = "SELL"
        score = bearish_score
        reasons = [
            "Bias H1 bearish.",
            "M15 membentuk setup SELL berdasarkan indikator teknikal.",
            (
                "Konfirmasi entry SELL tersedia dari M5."
                if m5_side == "SELL"
                else "Konfirmasi entry SELL tersedia dari order flow/aggTrades."
            ),
            f"Skor konfluensi SELL {score}/5 (minimum 3/5).",
        ]
        if bearish_structure:
            reasons.append("Struktur market mendukung skenario bearish.")
    else:
        side = "NO TRADE"
        score = max(bullish_score, bearish_score)
        reasons = [
            "Syarat minimum belum terpenuhi: H1 dan M15 harus searah, "
            "serta minimal satu konfirmasi entry dari M5 atau order flow/aggTrades.",
            "Konfirmasi eksekusi atau break struktur yang berlawanan memblokir entry.",
            f"Skor tertinggi saat ini {score}/5; minimum untuk sinyal adalah 3/5.",
        ]

    checks = {**bullish_checks, **bearish_checks}
    setup = m15
    trade_plan = None
    if side in {"BUY", "SELL"} and setup:
        entry = setup.get("entry")
        stop_loss = setup.get("stop_loss")
        valid_stop = (
            isinstance(entry, (int, float))
            and isinstance(stop_loss, (int, float))
            and entry > 0
            and ((side == "BUY" and stop_loss < entry) or (side == "SELL" and stop_loss > entry))
        )
        if valid_stop:
            risk = abs(float(entry) - float(stop_loss))
            target = float(entry) + risk * 1.5 if side == "BUY" else float(entry) - risk * 1.5
            trade_plan = {
                "entry": float(entry),
                "stop_loss": float(stop_loss),
                "take_profit": target,
                "risk_reward": 1.5,
                "source_timeframe": "15m",
                "method": "M15 ATR-based stop with fixed 1:1.5 risk/reward.",
            }
        else:
            side = "NO TRADE"
            reasons = [
                "Sinyal dibatalkan: level entry/SL M15 tidak valid sehingga " 
                "rasio risiko tidak aman."
            ]
            trade_plan = None

    context = market_context or {}
    cvd = context.get("cvd_history", {})
    order_book = context.get("order_book", {})
    max_confluence = 5
    oi_change = derivatives.get("open_interest_change_percent")
    funding = derivatives.get("funding_rate")
    context_notes = [
        "Open interest dan funding adalah konteks derivatif, bukan konfirmasi arah.",
    ]
    if derivatives.get("source_market") == "unavailable":
        context_notes.append(
            "Data derivatif tidak tersedia; nilai placeholder tidak digunakan sebagai "
            "konfirmasi BUY/SELL."
        )
    if trade_order_flow is not None:
        context_notes.append(
            "AggTrades mencakup batch terbaru; gunakan riwayat CVD persisten untuk konteks "
            "lebih panjang, dengan kemungkinan gap collector."
        )
    if cvd.get("note"):
        context_notes.append(cvd["note"])
    if order_book.get("note"):
        context_notes.append(order_book["note"])
    liquidations = context.get("liquidations", {})
    if liquidations.get("note"):
        context_notes.append(liquidations["note"])
    if liquidations.get("available"):
        context_notes.append(
            "Likuidasi teramati: short "
            f"{liquidations['short_liquidation_notional']:.2f} dan long "
            f"{liquidations['long_liquidation_notional']:.2f} notional; ini konteks, "
            "bukan sinyal arah tunggal."
        )
    if oi_change is None:
        context_notes.append("Perubahan open interest belum tersedia untuk dibandingkan.")
    elif oi_change > 0:
        context_notes.append(
            "Open interest meningkat; posisi terbuka bertambah, arah long/short tidak diketahui."
        )
    elif oi_change < 0:
        context_notes.append("Open interest menurun; posisi terbuka berkurang.")
    else:
        context_notes.append("Open interest relatif tidak berubah pada dua sampel terakhir.")

    if funding is not None:
        if funding > 0:
            context_notes.append("Funding positif: posisi long membayar posisi short.")
        elif funding < 0:
            context_notes.append("Funding negatif: posisi short membayar posisi long.")
        else:
            context_notes.append("Funding rate berada di sekitar nol.")

    score_note = (
        f"Skor adalah jumlah dari {max_confluence} kondisi konfirmasi; bukan probabilitas "
        "atau win-rate. OI/funding hanya konteks dan tidak menentukan arah."
    )
    return {
        "side": side,
        "confluence_score": score,
        "max_confluence": max_confluence,
        "score_note": score_note,
        "reasons": reasons,
        "context_notes": context_notes,
        "checks": checks,
        "strategy_mode": "DAY_TRADING",
        "trade_plan": trade_plan,
    }
