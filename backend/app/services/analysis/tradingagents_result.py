from typing import Any


RATING_TO_SIDE = {
    "Buy": "BUY",
    "Overweight": "BUY",
    "Hold": "NO TRADE",
    "Underweight": "SELL",
    "Sell": "SELL",
    "REVIEW": "NO TRADE",
}


def normalize_tradingagents_result(
    rating: str,
    final_decision: str = "",
    reports: dict[str, Any] | None = None,
) -> dict:
    """Map TradingAgents' five-tier research rating to a conservative app signal.

    TradingAgents ratings are research opinions, not executable orders. Hold or
    unparseable decisions therefore remain NO TRADE. No entry/SL/TP is invented.
    """
    normalized = rating.strip().capitalize() if isinstance(rating, str) else "REVIEW"
    if normalized not in RATING_TO_SIDE:
        normalized = "REVIEW"
    return {
        "engine": "TradingAgents",
        "rating": normalized,
        "side": RATING_TO_SIDE[normalized],
        "decision_text": final_decision.strip() if isinstance(final_decision, str) else "",
        "reports": reports or {},
        "execution_ready": False,
        "market_data_note": (
            "Bitget USDT-M Futures closed candles, order-book snapshot, open interest, "
            "and funding rate are injected into every TradingAgents analyst context. "
            "Upstream TradingAgents Yahoo tools remain supplemental and are not the "
            "authoritative source for exact futures prices."
        ),
        "risk_note": (
            "TradingAgents rating is research, not an exchange order. If agent and "
            "Bitget timeframes agree, V8 derives a candidate entry from the last "
            "closed 15m candle, SL at 1.5 x ATR(14), and TP at 1.5R. The plan still "
            "requires forward paper observation; live execution is disabled."
        ),
    }
