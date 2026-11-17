import pytest

from app.services.analysis.intelligence import build_intelligence_decision


def _tf(timeframe, side, price=None, ma_bias=None):
    direction = side if side in {"BUY", "SELL"} else ma_bias
    bullish = direction == "BUY"
    bearish = direction == "SELL"
    return {
        "timeframe": timeframe,
        "side": side,
        "entry": 100.0 if side != "NO TRADE" else None,
        "stop_loss": 98.0 if side == "BUY" else 102.0 if side == "SELL" else None,
        "take_profit": 103.0 if side == "BUY" else 97.0 if side == "SELL" else None,
        "risk_reward": 1.5 if side != "NO TRADE" else None,
        "indicators": {
            "last_price": price if price is not None else 105.0 if bullish else 95.0 if bearish else 100.0,
            "ma40": 100.0,
            "rsi16": 60.0 if bullish else 40.0 if bearish else 50.0,
            "ichimoku_above_cloud": bullish,
            "ichimoku_below_cloud": bearish,
        },
    }


def decide(h1="BUY", m15="BUY", m5="NO TRADE", flow="BUY_PRESSURE", structure="none"):
    analyses = [_tf("1h", h1), _tf("15m", m15), _tf("5m", m5)]
    return build_intelligence_decision(
        [h1, m15, m5],
        {"trend": "bullish", "event": structure},
        {"bias": "BALANCED"},
        {"source_market": "unavailable"},
        {"bias": flow},
        {},
        analyses,
    )


def test_buy_requires_h1_bias_m15_setup_and_m5_or_flow_trigger():
    result = decide()
    assert result["side"] == "BUY"
    assert result["strategy_mode"] == "ICHIMOKU_RSI16_MA40_H1_M15_M5"
    assert result["max_confluence"] == 5
    assert result["trade_plan"]["source_timeframe"] == "15m"
    assert result["trade_plan"]["risk_reward"] == 1.5
    assert result["trade_plan"]["take_profit"] == 103.0


def test_m5_trigger_can_confirm_without_orderflow():
    result = decide(m5="BUY", flow="BALANCED")
    assert result["side"] == "BUY"
    assert result["checks"]["m5_bullish_trigger"] is True


def test_sell_requires_h1_bias_m15_setup_and_m5_or_flow_trigger():
    result = decide("SELL", "SELL", "NO TRADE", "SELL_PRESSURE")
    assert result["side"] == "SELL"
    assert result["trade_plan"]["source_timeframe"] == "15m"


def test_misaligned_h1_and_m15_do_not_force_signal():
    assert decide(h1="SELL", m15="BUY")["side"] == "NO TRADE"
    assert decide(h1="BUY", m15="SELL")["side"] == "NO TRADE"


def test_missing_trigger_does_not_force_signal():
    assert decide(flow="BALANCED")["side"] == "NO TRADE"


def test_opposing_m5_or_orderflow_blocks_signal():
    assert decide(m5="SELL")["side"] == "NO TRADE"
    assert decide(flow="SELL_PRESSURE")["side"] == "NO TRADE"


def test_opposing_structure_blocks_signal():
    assert decide(structure="bearish_bos")["side"] == "NO TRADE"


def test_invalid_m15_stop_loss_cancels_trade():
    analyses = [_tf("1h", "BUY"), _tf("15m", "BUY"), _tf("5m", "BUY")]
    analyses[1]["stop_loss"] = 101.0
    result = build_intelligence_decision(
        ["BUY", "BUY", "BUY"],
        {"event": "none"},
        {"bias": "BALANCED"},
        {"source_market": "unavailable"},
        {"bias": "BALANCED"},
        {},
        analyses,
    )
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_unknown_technical_side_is_rejected():
    with pytest.raises(ValueError):
        build_intelligence_decision(["LONG"], {}, {}, {})
