from app.services.trade_lifecycle import advance_lifecycle, build_lifecycle


def plan():
    return {
        "entry": 100.0,
        "stop_loss": 98.0,
        "take_profit_1": 102.0,
        "take_profit_2": 104.0,
        "take_profit_3": 106.0,
        "take_profit": 106.0,
    }


def test_tp1_then_breakeven_stop_is_a_net_positive_paper_win():
    state, changed = advance_lifecycle("BUY", plan(), None, 102.2, 100.5, "c1")
    assert changed
    assert state["remaining_position_pct"] == 50.0
    assert state["current_stop"] == 100.0
    assert state["realized_r"] == 0.38675

    state, changed = advance_lifecycle("BUY", plan(), state, 101.0, 99.9, "c2")
    assert changed
    assert state["closed"] is True
    assert state["outcome"] == "WIN"
    assert state["realized_r"] == 0.34925
    assert state["closed_position_pct"] == 100.0


def test_tp1_tp2_then_stop_at_tp1_keeps_partial_profit():
    state, _ = advance_lifecycle("BUY", plan(), None, 102.2, 100.5, "c1")
    state, _ = advance_lifecycle("BUY", plan(), state, 104.2, 102.5, "c2")
    assert state["remaining_position_pct"] == 20.0
    assert state["current_stop"] == 102.0
    state, _ = advance_lifecycle("BUY", plan(), state, 103.0, 101.9, "c3")
    assert state["closed"] is True
    assert state["outcome"] == "WIN"
    assert state["realized_r"] == 1.14805


def test_all_three_targets_close_50_30_20_position():
    state, _ = advance_lifecycle("BUY", plan(), None, 102.2, 100.5, "c1")
    state, _ = advance_lifecycle("BUY", plan(), state, 104.2, 102.5, "c2")
    state, _ = advance_lifecycle("BUY", plan(), state, 106.2, 103.0, "c3")
    assert state["closed"] is True
    assert state["remaining_position_pct"] == 0.0
    assert state["closed_position_pct"] == 100.0
    assert state["outcome"] == "WIN"
    assert state["realized_r"] == 1.54745


def test_stop_before_tp1_is_full_loss():
    state, changed = advance_lifecycle(
        "BUY", plan(), build_lifecycle("BUY", plan()), 100.5, 97.9, "c1"
    )
    assert changed
    assert state["outcome"] == "LOSS"
    assert state["realized_r"] == -1.1485


def test_same_candle_stop_and_target_resolves_conservatively_as_stop():
    state, _ = advance_lifecycle("BUY", plan(), None, 102.5, 97.5, "c1")
    assert state["closed"] is True
    assert state["outcome"] == "LOSS"
    assert state["ambiguous_candle"] is True
    assert state["realized_r"] == -1.1485


def test_duplicate_candle_does_not_duplicate_partial_fill():
    state, _ = advance_lifecycle("BUY", plan(), None, 102.5, 100.5, "c1")
    repeated, changed = advance_lifecycle("BUY", plan(), state, 102.5, 100.5, "c1")
    assert changed is False
    assert repeated["realized_r"] == 0.38675
    assert len(repeated["events"]) == 1


def test_sell_partial_ladder_uses_symmetric_stop_management_and_costs():
    sell_plan = {
        "entry": 100.0,
        "stop_loss": 102.0,
        "take_profit": 97.0,
    }
    state, _ = advance_lifecycle("SELL", sell_plan, None, 99.5, 97.8, "s1")
    assert state["remaining_position_pct"] == 50.0
    assert state["current_stop"] == 100.0
    assert state["realized_r"] == 0.38825

    state, _ = advance_lifecycle("SELL", sell_plan, state, 97.5, 95.8, "s2")
    assert state["remaining_position_pct"] == 20.0
    assert state["current_stop"] == 98.0

    state, _ = advance_lifecycle("SELL", sell_plan, state, 98.1, 97.5, "s3")
    assert state["closed"] is True
    assert state["outcome"] == "WIN"
    assert state["realized_r"] == 1.15195
