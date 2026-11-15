from math import isfinite


def summarize_cvd_history(history: dict, lookback: int = 15) -> dict:
    points = history.get("points", [])[-lookback:]
    if not points:
        return {
            "available": False,
            "bias": "UNAVAILABLE",
            "bucket_count": 0,
            "net_delta": 0.0,
            "delta_percent": 0.0,
            "note": "Belum ada riwayat CVD tersimpan.",
        }
    buy = sum(float(point["buy_volume"]) for point in points)
    sell = sum(float(point["sell_volume"]) for point in points)
    if not all(isfinite(value) and value >= 0 for value in (buy, sell)):
        raise ValueError("CVD history contains invalid volume.")
    total = buy + sell
    delta = buy - sell
    percent = delta / total * 100 if total else 0.0
    bias = "BUY_PRESSURE" if percent >= 5 else (
        "SELL_PRESSURE" if percent <= -5 else "BALANCED"
    )
    return {
        "available": True,
        "bias": bias,
        "bucket_count": len(points),
        "net_delta": delta,
        "delta_percent": percent,
        "note": (
            "Bias dihitung dari bucket CVD yang tersimpan; kualitasnya bergantung "
            "pada kelengkapan collector dan dapat memiliki gap."
        ),
    }


def summarize_liquidations(history: dict) -> dict:
    points = history.get("points", [])
    buy_notional = sum(
        float(point["total_notional"]) for point in points if point["side"] == "BUY"
    )
    sell_notional = sum(
        float(point["total_notional"]) for point in points if point["side"] == "SELL"
    )
    if not all(isfinite(value) and value >= 0 for value in (buy_notional, sell_notional)):
        raise ValueError("Liquidation history contains invalid notional.")
    return {
        "available": bool(points),
        "event_count": int(history.get("event_count", 0)),
        "short_liquidation_notional": buy_notional,
        "long_liquidation_notional": sell_notional,
        "observed_notional": buy_notional + sell_notional,
        "note": (
            "BUY force-order dihitung sebagai short liquidation dan SELL sebagai long "
            "liquidation. Ini hanya event yang tertangkap Binance, bukan total pasar."
        ),
    }
