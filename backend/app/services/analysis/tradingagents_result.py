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
            "This adapter uses TradingAgents' upstream crypto data path (Yahoo Finance "
            "reference data); it is not Bitget USD-M futures, order-book, or open-interest data."
        ),
        "risk_note": (
            "TradingAgents provides a research rating, not exchange order levels. "
            "A separate validated risk plan and paper-execution check are required."
        ),
    }
