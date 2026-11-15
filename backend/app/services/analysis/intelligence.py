def build_intelligence_decision(
    technical_sides: list[str],
    structure: dict,
    order_flow: dict,
    derivatives: dict,
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

    if all(bullish_checks):
        side = "BUY"
        reasons = [
            "Seluruh timeframe teknikal yang diminta memberi sinyal BUY.",
            "Struktur pasar mendukung arah bullish tanpa event bearish yang berlawanan.",
            "Order-flow proxy menunjukkan tekanan beli pada lookback terpilih.",
        ]
        score = sum(bullish_checks)
    elif all(bearish_checks):
        side = "SELL"
        reasons = [
            "Seluruh timeframe teknikal yang diminta memberi sinyal SELL.",
            "Struktur pasar mendukung arah bearish tanpa event bullish yang berlawanan.",
            "Order-flow proxy menunjukkan tekanan jual pada lookback terpilih.",
        ]
        score = sum(bearish_checks)
    else:
        side = "NO TRADE"
        score = max(sum(bullish_checks), sum(bearish_checks))
        reasons = [
            "Konfirmasi teknikal, struktur, dan order flow belum seluruhnya searah.",
            "Sistem memilih NO TRADE daripada memaksakan sinyal dari indikator yang terpisah.",
        ]

    oi_change = derivatives.get("open_interest_change_percent")
    funding = derivatives.get("funding_rate")
    context_notes = [
        "Open interest dan funding ditampilkan sebagai konteks derivatif, bukan konfirmasi arah.",
    ]
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

    return {
        "side": side,
        "confluence_score": score,
        "max_confluence": 3,
        "score_note": (
            "Skor adalah jumlah dari tiga kondisi konfirmasi (timeframe teknikal, "
            "struktur, order-flow proxy), bukan probabilitas atau win-rate. OI/funding "
            "hanya konteks dan tidak menentukan arah."
        ),
        "reasons": reasons,
        "context_notes": context_notes,
        "checks": {
            "technical_bullish_alignment": all_bullish,
            "technical_bearish_alignment": all_bearish,
            "bullish_structure": bullish_structure,
            "bearish_structure": bearish_structure,
            "buy_pressure": order_flow.get("bias") == "BUY_PRESSURE",
            "sell_pressure": order_flow.get("bias") == "SELL_PRESSURE",
        },
    }
