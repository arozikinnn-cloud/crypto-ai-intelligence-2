def build_intelligence_decision(
    technical_sides: list[str],
    structure: dict,
    order_flow: dict,
    derivatives: dict,
    trade_order_flow: dict | None = None,
    market_context: dict | None = None,
) -> dict:
    if not technical_sides:
        raise ValueError("At least one technical timeframe is required.")
    if any(side not in {"BUY", "SELL", "NO TRADE"} for side in technical_sides):
        raise ValueError("Technical timeframe contains an unsupported decision.")

    all_bullish = all(side == "BUY" for side in technical_sides)
    all_bearish = all(side == "SELL" for side in technical_sides)
    structure_event = structure.get("event", "none")
    structure_trend = structure.get("trend", "range_or_unconfirmed")

    bullish_structure = (
        structure_event in {"bullish_bos", "bullish_choch"}
        or (
            structure_event not in {"bearish_bos", "bearish_choch"}
            and structure_trend == "bullish"
        )
    )
    bearish_structure = (
        structure_event in {"bearish_bos", "bearish_choch"}
        or (
            structure_event not in {"bullish_bos", "bullish_choch"}
            and structure_trend == "bearish"
        )
    )

    bullish_checks = [
        all_bullish,
        bullish_structure,
        order_flow.get("bias") == "BUY_PRESSURE",
    ]
    bearish_checks = [
        all_bearish,
        bearish_structure,
        order_flow.get("bias") == "SELL_PRESSURE",
    ]
    checks = {
        "technical_bullish_alignment": all_bullish,
        "technical_bearish_alignment": all_bearish,
        "bullish_structure": bullish_structure,
        "bearish_structure": bearish_structure,
        "buy_pressure_kline": order_flow.get("bias") == "BUY_PRESSURE",
        "sell_pressure_kline": order_flow.get("bias") == "SELL_PRESSURE",
    }

    if trade_order_flow is not None:
        trade_buy = trade_order_flow.get("bias") == "BUY_PRESSURE"
        trade_sell = trade_order_flow.get("bias") == "SELL_PRESSURE"
        bullish_checks.append(trade_buy)
        bearish_checks.append(trade_sell)
        checks["buy_pressure_aggtrades"] = trade_buy
        checks["sell_pressure_aggtrades"] = trade_sell

    context = market_context or {}
    cvd = context.get("cvd_history", {})
    if cvd.get("available"):
        cvd_buy = cvd.get("bias") == "BUY_PRESSURE"
        cvd_sell = cvd.get("bias") == "SELL_PRESSURE"
        bullish_checks.append(cvd_buy)
        bearish_checks.append(cvd_sell)
        checks["buy_pressure_persistent_cvd"] = cvd_buy
        checks["sell_pressure_persistent_cvd"] = cvd_sell

    order_book = context.get("order_book", {})
    if order_book.get("available"):
        book_buy = order_book.get("bias") == "BUY_DEPTH"
        book_sell = order_book.get("bias") == "SELL_DEPTH"
        bullish_checks.append(book_buy)
        bearish_checks.append(book_sell)
        checks["buy_depth_order_book"] = book_buy
        checks["sell_depth_order_book"] = book_sell

    max_confluence = len(bullish_checks)
    if all(bullish_checks):
        side = "BUY"
        score = max_confluence
        reasons = [
            "Seluruh timeframe teknikal yang diminta memberi sinyal BUY.",
            "Struktur pasar mendukung arah bullish.",
            "Order-flow kline menunjukkan tekanan beli.",
        ]
        if trade_order_flow is not None:
            reasons.append("Data Binance Spot aggTrades juga menunjukkan tekanan beli.")
        if cvd.get("available"):
            reasons.append("Riwayat CVD tersimpan mengonfirmasi tekanan beli.")
        if order_book.get("available"):
            reasons.append("Snapshot order book menunjukkan kedalaman bid lebih besar.")
    elif all(bearish_checks):
        side = "SELL"
        score = max_confluence
        reasons = [
            "Seluruh timeframe teknikal yang diminta memberi sinyal SELL.",
            "Struktur pasar mendukung arah bearish.",
            "Order-flow kline menunjukkan tekanan jual.",
        ]
        if trade_order_flow is not None:
            reasons.append("Data Binance Spot aggTrades juga menunjukkan tekanan jual.")
        if cvd.get("available"):
            reasons.append("Riwayat CVD tersimpan mengonfirmasi tekanan jual.")
        if order_book.get("available"):
            reasons.append("Snapshot order book menunjukkan kedalaman ask lebih besar.")
    else:
        side = "NO TRADE"
        score = max(sum(bullish_checks), sum(bearish_checks))
        reasons = [
            "Konfirmasi teknikal, struktur, dan order flow belum seluruhnya searah.",
            "Sistem memilih NO TRADE daripada memaksakan sinyal.",
        ]
        if trade_order_flow is not None and trade_buy != trade_sell:
            reasons.append(
                "Tekanan transaksi aggTrades tidak mengonfirmasi kedua sisi secara bersamaan."
            )

    oi_change = derivatives.get("open_interest_change_percent")
    funding = derivatives.get("funding_rate")
    context_notes = [
        "Open interest dan funding adalah konteks derivatif, bukan konfirmasi arah.",
    ]
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
    }
