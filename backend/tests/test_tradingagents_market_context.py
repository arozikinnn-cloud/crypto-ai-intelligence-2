from datetime import datetime, timezone

from app.services.analysis.tradingagents_market_context import finalize_v8_decision


def _context(side="BUY"):
    timeframes = {}
    for timeframe in ("1h", "30m", "15m", "5m"):
        timeframes[timeframe] = {
            "side": side,
            "entry": 100.0,
            "stop_loss": 98.0,
            "take_profit": 103.0,
            "risk_reward": 1.5,
            "confluence_score": 4,
            "reasons": ["MA40, RSI16, Ichimoku confirmed."],
            "indicators": {"last_price": 100.0},
            "candle_close_time": "2026-11-18T00:00:00+00:00",
            "candle_count": 120,
        }
    return {
        "provider": "bitget_usdt_futures",
        "symbol": "BTCUSDT",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "timeframes": timeframes,
        "derivatives": {"open_interest": 1000, "funding_rate": 0.0001},
        "order_book": {"imbalance": 0.1},
        "context_text": "Verified Bitget market data.",
    }


def test_v8_requires_tradingagents_and_all_higher_timeframes_to_agree():
    result = finalize_v8_decision("Buy", "Buy", {}, _context())
    assert result["side"] == "BUY"
    assert result["trade_plan"]["entry"] == 100
    assert result["trade_plan"]["stop_loss"] == 98
    assert result["trade_plan"]["take_profit"] == 106
    assert result["trade_plan"]["risk_reward"] == 3.0
    assert result["execution_ready"] is False
    assert result["paper_validation_required"] is True


def test_v8_fails_closed_when_agent_and_bitget_disagree():
    result = finalize_v8_decision("Buy", "Buy", {}, _context("SELL"))
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_v8_does_not_create_trade_plan_for_hold_rating():
    result = finalize_v8_decision("Hold", "Hold", {}, _context())
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_v8_does_not_create_trade_plan_when_five_minute_conflicts():
    context = _context()
    context["timeframes"]["5m"]["side"] = "SELL"
    result = finalize_v8_decision("Buy", "Buy", {}, context)
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None
