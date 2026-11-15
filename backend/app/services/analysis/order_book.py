from math import isfinite


def analyze_order_book(snapshot: dict, depth_levels: int = 20) -> dict:
    if not 1 <= depth_levels <= 100:
        raise ValueError("depth_levels must be between 1 and 100.")
    bids = snapshot.get("bids", [])[:depth_levels]
    asks = snapshot.get("asks", [])[:depth_levels]
    if not bids or not asks:
        raise ValueError("Both bid and ask depth are required.")

    def notional(levels):
        total = 0.0
        for level in levels:
            if len(level) != 2:
                raise ValueError("Malformed order-book level.")
            price, quantity = float(level[0]), float(level[1])
            if not isfinite(price) or not isfinite(quantity) or price <= 0 or quantity < 0:
                raise ValueError("Invalid order-book level.")
            total += price * quantity
        return total

    bid_notional = notional(bids)
    ask_notional = notional(asks)
    total = bid_notional + ask_notional
    imbalance = (bid_notional - ask_notional) / total if total else 0.0
    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    if best_bid >= best_ask:
        raise ValueError("Order book is crossed or locked.")
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10000
    bias = "BUY_DEPTH" if imbalance >= 0.10 else (
        "SELL_DEPTH" if imbalance <= -0.10 else "BALANCED"
    )
    return {
        "symbol": snapshot["symbol"],
        "source_market": "binance_spot_order_book_snapshot",
        "depth_levels": min(len(bids), len(asks)),
        "bid_notional": bid_notional,
        "ask_notional": ask_notional,
        "imbalance": imbalance,
        "imbalance_percent": imbalance * 100,
        "spread_bps": spread_bps,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "bias": bias,
        "method_note": (
            "Imbalance adalah perbandingan notional bid/ask pada satu snapshot. "
            "Ini bukan bukti absorption, spoofing, niat pelaku, atau riwayat DOM; "
            "likuiditas dapat berubah atau dibatalkan."
        ),
    }
