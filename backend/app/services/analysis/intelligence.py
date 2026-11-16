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
    h4 = by_tf.get("4h", {})
    h1 = by_tf.get("1h", {})
    m15 = by_tf.get("15m", {})
    h4_side, h1_side, setup_side = h4.get("side"), h1.get("side"), m15.get("side")

    # Day-trading hierarchy: H4/H1 establish directional bias, M15 supplies
    # the setup, and M5/aggTrades provide a short-term execution confirmation.
    htf_buy = h4_side == "BUY" and h1_side == "BUY"
    htf_sell = h4_side == "SELL" and h1_side == "SELL"
    flow_buy = order_flow.get("bias") == "BUY_PRESSURE"
    flow_sell = order_flow.get("bias") == "SELL_PRESSURE"
    tape_buy = (trade_order_flow or {}).get("bias") == "BUY_PRESSURE"
    tape_sell = (trade_order_flow or {}).get("bias") == "SELL_PRESSURE"
    buy_trigger = flow_buy or tape_buy
    sell_trigger = flow_sell or tape_sell

    bullish_structure = (
        structure.get("event") in {"bullish_bos", "bullish_choch"}
        or structure.get("trend") == "bullish"
    )
    bearish_structure = (
        structure.get("event") in {"bearish_bos", "bearish_choch"}
        or structure.get("trend") == "bearish"
    )
    bullish_checks = {
        "h4_bullish_bias": h4_side == "BUY",
        "h1_bullish_bias": h1_side == "BUY",
        "m15_buy_setup": setup_side == "BUY",
        "m5_or_tape_buy_confirmation": buy_trigger,
        "bullish_market_structure": bullish_structure,
    }
    bearish_checks = {
        "h4_bearish_bias": h4_side == "SELL",
        "h1_bearish_bias": h1_side == "SELL",
        "m15_sell_setup": setup_side == "SELL",
        "m5_or_tape_sell_confirmation": sell_trigger,
        "bearish_market_structure": bearish_structure,
    }

    if htf_buy and setup_side == "BUY" and buy_trigger:
        side = "BUY"
        score = sum(bullish_checks.values())
        reasons = [
            "Bias H4 dan H1 searah bullish.",
            "M15 membentuk setup BUY berdasarkan indikator teknikal.",
            "Order flow M5 atau transaksi aggTrades mengonfirmasi tekanan beli.",
        ]
        if bullish_structure:
            reasons.append("Struktur H1 mendukung skenario bullish.")
    elif htf_sell and setup_side == "SELL" and sell_trigger:
        side = "SELL"
        score = sum(bearish_checks.values())
        reasons = [
            "Bias H4 dan H1 searah bearish.",
            "M15 membentuk setup SELL berdasarkan indikator teknikal.",
            "Order flow M5 atau transaksi aggTrades mengonfirmasi tekanan jual.",
        ]
        if bearish_structure:
            reasons.append("Struktur H1 mendukung skenario bearish.")
    else:
        side = "NO TRADE"
        score = max(sum(bullish_checks.values()), sum(bearish_checks.values()))
        reasons = [
            "Syarat Day Trading belum lengkap: H4 dan H1 harus searah, M15 harus memberi setup, serta M5/aggTrades harus mengonfirmasi.",
            "Sistem tidak memaksakan entry ketika konfirmasi belum terpenuhi.",
        ]

    checks = {**bullish_checks, **bearish_checks}
    setup = m15
    trade_plan = None
    if side in {"BUY", "SELL"} and setup:
        trade_plan = {
            "entry": setup.get("entry"),
            "stop_loss": setup.get("stop_loss"),
            "take_profit": setup.get("take_profit"),
            "risk_reward": setup.get("risk_reward"),
            "source_timeframe": "15m",
            "method": "M15 ATR-based stop with 2R target; review before execution.",
        }

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
