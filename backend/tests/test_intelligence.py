import pytest
from app.services.analysis.intelligence import build_intelligence_decision


def _tf(timeframe, side, ma_bias=None):
    buy = side == "BUY" or ma_bias == "BUY"
    sell = side == "SELL" or ma_bias == "SELL"
    return {
        "timeframe": timeframe, "side": side,
        "entry": 100.0 if side != "NO TRADE" else None,
        "stop_loss": 98.0 if side == "BUY" else 102.0 if side == "SELL" else None,
        "take_profit": 103.0 if side == "BUY" else 97.0 if side == "SELL" else None,
        "risk_reward": 1.5 if side != "NO TRADE" else None,
        "indicators": {
            "last_price": 105.0 if buy else 95.0 if sell else 100.0,
            "ma40": 100.0,
            "ichimoku_above_cloud": buy,
            "ichimoku_below_cloud": sell,
        },
    }


def decide(m15="BUY", m30="BUY", flow="BALANCED", structure="none"):
    analyses = [_tf("15m", m15), _tf("30m", m30)]
    return build_intelligence_decision(
        [m15, m30], {"trend": "range_or_unconfirmed", "event": structure},
        {"bias": flow}, {"source_market": "unavailable"},
        {"bias": "BALANCED"}, {}, analyses,
    )


def test_buy_requires_m15_setup_and_m30_bias():
    result = decide()
    assert result["side"] == "BUY"
    assert result["strategy_mode"] == "ICHIMOKU_RSI16_MA40_M15_M30"
    assert result["trade_plan"]["source_timeframe"] == "15m"
    assert result["trade_plan"]["risk_reward"] == 1.5
    assert result["trade_plan"]["take_profit"] == 103.0


def test_sell_requires_m15_setup_and_m30_bias():
    result = decide("SELL", "SELL")
    assert result["side"] == "SELL"
    assert result["trade_plan"]["source_timeframe"] == "15m"


def test_misaligned_timeframes_do_not_force_signal():
    assert decide("SELL", "BUY")["side"] == "NO TRADE"
    assert decide("BUY", "SELL")["side"] == "NO TRADE"


def test_orderflow_conflict_blocks_buy():
    result = decide("BUY", "BUY", flow="SELL_PRESSURE")
    assert result["side"] == "NO TRADE"


def test_orderflow_conflict_blocks_sell():
    result = decide("SELL", "SELL", flow="BUY_PRESSURE")
    assert result["side"] == "NO TRADE"


def test_supportive_orderflow_and_structure_are_context():
    result = decide("BUY", "BUY", flow="BUY_PRESSURE", structure="bullish_bos")
    assert result["side"] == "BUY"
    assert result["checks"]["buy_orderflow_confirmation"] is True


def test_opposing_structure_blocks_signal():
    assert decide("BUY", "BUY", structure="bearish_bos")["side"] == "NO TRADE"


def test_invalid_m15_stop_loss_cancels_trade():
    analyses = [_tf("15m", "BUY"), _tf("30m", "BUY")]
    analyses[0]["stop_loss"] = 101.0
    result = build_intelligence_decision(
        ["BUY", "BUY"], {"event": "none"}, {"bias": "BALANCED"},
        {"source_market": "unavailable"}, {"bias": "BALANCED"}, {}, analyses,
    )
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_unknown_technical_side_is_rejected():
    with pytest.raises(ValueError):
        build_intelligence_decision(["LONG"], {}, {}, {})
