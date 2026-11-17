from app.services.analysis.intelligence import build_intelligence_decision


def _analysis(timeframe, side):
    buy = side == "BUY"
    sell = side == "SELL"
    return {
        "timeframe": timeframe,
        "side": side,
        "entry": 100.0 if side != "NO TRADE" else None,
        "stop_loss": 98.0 if buy else 102.0 if sell else None,
        "take_profit": 103.0 if buy else 97.0 if sell else None,
        "risk_reward": 1.5 if side != "NO TRADE" else None,
        "indicators": {
            "last_price": 105.0 if buy else 95.0 if sell else 100.0,
            "ma40": 100.0,
            "ichimoku_above_cloud": buy,
            "ichimoku_below_cloud": sell,
        },
    }


def _decision(m15_side="BUY", m30_side="BUY", flow="BUY_PRESSURE"):
    analyses = [
        _analysis("15m", m15_side),
        _analysis("30m", m30_side),
    ]
    return build_intelligence_decision(
        [item["side"] for item in analyses],
        {"trend": "bullish", "event": "bullish_bos"},
        {"bias": flow},
        {"source_market": "unavailable"},
        {"bias": "BALANCED"},
        {},
        analyses,
    )


def test_strategy_buy_requires_m30_bias_and_m15_setup():
    result = _decision()
    assert result["side"] == "BUY"
    assert result["strategy_mode"] == "ICHIMOKU_RSI16_MA40_M15_M30"
    assert result["trade_plan"]["source_timeframe"] == "15m"
    assert result["trade_plan"]["risk_reward"] == 1.5


def test_strategy_blocks_when_m30_bias_conflicts():
    result = _decision(m15_side="BUY", m30_side="SELL")
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_strategy_blocks_without_m15_setup():
    result = _decision(m15_side="NO TRADE", m30_side="BUY")
    assert result["side"] == "NO TRADE"


def test_strategy_blocks_opposing_orderflow():
    result = _decision(flow="SELL_PRESSURE")
    assert result["side"] == "NO TRADE"
