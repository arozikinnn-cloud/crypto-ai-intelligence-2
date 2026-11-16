from app.services.analysis.intelligence import build_intelligence_decision


def _analysis(timeframe, side):
    return {
        "timeframe": timeframe,
        "side": side,
        "entry": 100.0 if side != "NO TRADE" else None,
        "stop_loss": 98.0 if side == "BUY" else 102.0 if side == "SELL" else None,
        "take_profit": 104.0 if side == "BUY" else 96.0 if side == "SELL" else None,
        "risk_reward": 2.0 if side != "NO TRADE" else None,
    }


def _decision(analyses):
    return build_intelligence_decision(
        [item["side"] for item in analyses],
        {"trend": "bullish", "event": "bullish_bos"},
        {"bias": "BUY_PRESSURE"},
        {"source_market": "unavailable"},
        {"bias": "BALANCED"},
        {},
        analyses,
    )


def test_day_trading_buy_requires_h4_h1_m15_and_flow_confirmation():
    result = _decision([
        _analysis("4h", "BUY"),
        _analysis("1h", "BUY"),
        _analysis("15m", "BUY"),
    ])
    assert result["side"] == "BUY"
    assert result["strategy_mode"] == "DAY_TRADING"
    assert result["trade_plan"]["source_timeframe"] == "15m"
    assert result["trade_plan"]["risk_reward"] == 2.0


def test_day_trading_does_not_force_signal_when_higher_timeframes_conflict():
    result = _decision([
        _analysis("4h", "BUY"),
        _analysis("1h", "SELL"),
        _analysis("15m", "BUY"),
    ])
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_day_trading_does_not_force_signal_without_m15_setup():
    result = _decision([
        _analysis("4h", "BUY"),
        _analysis("1h", "BUY"),
        _analysis("15m", "NO TRADE"),
    ])
    assert result["side"] == "NO TRADE"
