def build_intelligence_decision(
    technical_sides: list[str],
    structure: dict,
    order_flow: dict,
    derivatives: dict,
) -> dict:
    if not technical_sides:
        raise ValueError("At least one technical timeframe is required.")

    all_bullish = all(side == "BUY" for side in technical_sides)
    all_bearish = all(side == "SELL" for side in technical_sides)
    oi_change = derivatives.get("open_interest_change_percent")
    funding = derivatives.get("funding_rate")
    bullish_checks = [
        all_bullish,
        structure.get("trend") == "bullish" or structure.get("event") == "bullish_bos",
        order_flow.get("bias") == "BUY_PRESSURE",
        oi_change is not None and oi_change > 0,
        funding is not None and funding < 0.0005,
    ]
    bearish_checks = [
        all_bearish,
        structure.get("trend") == "bearish" or structure.get("event") == "bearish_bos",
        order_flow.get("bias") == "SELL_PRESSURE",
        oi_change is not None and oi_change > 0,
        funding is not None and funding > -0.0005,
    ]

    if all(bullish_checks):
        side = "BUY"
        reasons = [
            "Seluruh timeframe teknikal memberi sinyal BUY.",
            "Struktur pasar mendukung arah bullish.",
            "Order flow menunjukkan tekanan beli agresif.",
            "Open interest meningkat pada periode pengamatan.",
            "Funding tidak berada di level positif ekstrem menurut ambang heuristik.",
        ]
    elif all(bearish_checks):
        side = "SELL"
        reasons = [
            "Seluruh timeframe teknikal memberi sinyal SELL.",
            "Struktur pasar mendukung arah bearish.",
            "Order flow menunjukkan tekanan jual agresif.",
            "Open interest meningkat pada periode pengamatan.",
            "Funding tidak berada di level negatif ekstrem menurut ambang heuristik.",
        ]
    else:
        side = "NO TRADE"
        reasons = [
            "Konfirmasi lintas modul belum lengkap atau saling bertentangan.",
            "Sistem tidak mengubah satu indikator tunggal menjadi sinyal entry.",
        ]

    score = max(sum(bullish_checks), sum(bearish_checks))
    return {
        "side": side,
        "confluence_score": score,
        "max_confluence": 5,
        "score_note": (
            "Skor adalah jumlah kondisi heuristik yang cocok, bukan probabilitas "
            "kemenangan atau rekomendasi investasi."
        ),
        "reasons": reasons,
        "checks": {
            "technical_alignment": all_bullish if side != "SELL" else all_bearish,
            "market_structure": bullish_checks[1] if side != "SELL" else bearish_checks[1],
            "order_flow": bullish_checks[2] if side != "SELL" else bearish_checks[2],
            "open_interest_rising": bullish_checks[3] if side != "SELL" else bearish_checks[3],
            "funding_filter": bullish_checks[4] if side != "SELL" else bearish_checks[4],
        },
    }
