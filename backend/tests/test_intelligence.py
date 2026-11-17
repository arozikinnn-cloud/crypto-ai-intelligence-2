import pytest

from app.services.analysis.intelligence import build_intelligence_decision


def _tf(timeframe, side):
    return {
        "timeframe": timeframe,
        "side": side,
        "entry": 100.0 if side != "NO TRADE" else None,
        "stop_loss": 98.0 if side == "BUY" else 102.0 if side == "SELL" else None,
        "take_profit": 104.0 if side == "BUY" else 96.0 if side == "SELL" else None,
        "risk_reward": 1.5 if side != "NO TRADE" else None,
    }


def decide(sides, flow="BUY_PRESSURE", tape="BALANCED", structure="bullish"):
    analyses = [_tf(tf, side) for tf, side in zip(("5m", "15m", "1h"), sides)]
    return build_intelligence_decision(
        sides,
        {"trend": structure, "event": "none"},
        {"bias": flow},
        {"source_market": "unavailable", "funding_rate": 0.0001},
        {"bias": tape},
        {},
        analyses,
    )


def test_day_trading_buy_requires_aligned_higher_timeframes_setup_and_flow():
    result = decide(["BUY", "BUY", "BUY"])
    assert result["side"] == "BUY"
    assert result["strategy_mode"] == "DAY_TRADING"
    assert result["trade_plan"]["source_timeframe"] == "15m"
    assert result["trade_plan"]["risk_reward"] == 1.5
    assert result["max_confluence"] == 5
    assert result["trade_plan"]["take_profit"] == 103.0


def test_day_trading_sell_requires_aligned_higher_timeframes_setup_and_flow():
    result = decide(["SELL", "SELL", "SELL"], flow="SELL_PRESSURE", structure="bearish")
    assert result["side"] == "SELL"
    assert result["trade_plan"]["source_timeframe"] == "15m"


def test_conflicting_higher_timeframes_never_force_signal():
    result = decide(["BUY", "SELL", "BUY"])
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_missing_m15_setup_never_forces_signal():
    result = decide(["BUY", "NO TRADE", "BUY"])
    assert result["side"] == "NO TRADE"


def test_conflicting_kline_and_tape_flow_blocks_signal():
    result = decide(["BUY", "BUY", "BUY"], flow="BUY_PRESSURE", tape="SELL_PRESSURE")
    assert result["side"] == "NO TRADE"
    assert result["checks"]["m5_or_tape_buy_confirmation"] is False


def test_m5_no_trade_can_use_directional_order_flow_confirmation():
    result = decide(
        ["NO TRADE", "SELL", "SELL"],
        flow="SELL_PRESSURE",
        tape="BALANCED",
        structure="range_or_unconfirmed",
    )
    assert result["side"] == "SELL"
    assert result["confluence_score"] == 3
    assert result["max_confluence"] == 5
    assert result["trade_plan"]["source_timeframe"] == "15m"


def test_m5_confirmation_can_be_enough_without_structure_or_flow():
    result = decide(
        ["BUY", "BUY", "BUY"],
        flow="BALANCED",
        tape="BALANCED",
        structure="range_or_unconfirmed",
    )
    assert result["side"] == "BUY"
    assert result["confluence_score"] == 3


def test_no_m5_or_order_flow_confirmation_stays_no_trade():
    result = decide(
        ["NO TRADE", "BUY", "BUY"],
        flow="BALANCED",
        tape="BALANCED",
        structure="range_or_unconfirmed",
    )
    assert result["side"] == "NO TRADE"
    assert result["trade_plan"] is None


def test_opposite_m5_confirmation_blocks_signal():
    result = decide(
        ["SELL", "BUY", "BUY"],
        flow="BUY_PRESSURE",
        tape="BUY_PRESSURE",
        structure="bullish",
    )
    assert result["side"] == "NO TRADE"


def test_derivatives_are_context_not_directional_confirmation():
    result = decide(["BUY", "BUY", "BUY"])
    assert result["side"] == "BUY"
    assert any("Funding positif" in note for note in result["context_notes"])


def test_unknown_technical_side_is_rejected():
    with pytest.raises(ValueError, match="unsupported"):
        build_intelligence_decision(["LONG"], {}, {}, {})
