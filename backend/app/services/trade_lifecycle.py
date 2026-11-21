"""Deterministic paper-tracked partial exits for V8 signal lifecycle.

This module never submits exchange orders. It records price-triggered paper
fills from closed OHLC candles and resolves same-candle stop/target ambiguity
conservatively in favor of the stop.
"""
from __future__ import annotations


def _valid_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def build_lifecycle(side: str, plan: dict) -> dict:
    entry = float(plan["entry"])
    initial_stop = float(plan["stop_loss"])
    risk = abs(entry - initial_stop)
    if risk <= 0:
        raise ValueError("Risk distance must be positive.")
    direction = 1.0 if side == "BUY" else -1.0
    fallback = [
        entry + direction * risk,
        entry + direction * risk * 2,
        entry + direction * risk * 3,
    ]
    targets = [
        plan.get("take_profit_1", fallback[0]),
        plan.get("take_profit_2", fallback[1]),
        plan.get("take_profit_3", plan.get("take_profit", fallback[2])),
    ]
    targets = [float(value) for value in targets]
    if side == "BUY" and not (entry < targets[0] < targets[1] < targets[2]):
        raise ValueError("BUY partial targets must be strictly ascending above entry.")
    if side == "SELL" and not (entry > targets[0] > targets[1] > targets[2]):
        raise ValueError("SELL partial targets must be strictly descending below entry.")
    return {
        "version": 1,
        "mode": "PAPER_PRICE_TRACKING",
        "initial_position_pct": 100.0,
        "remaining_position_pct": 100.0,
        "closed_position_pct": 0.0,
        "current_stop": initial_stop,
        "targets": targets,
        "target_allocations_pct": [50.0, 30.0, 20.0],
        "next_target_index": 0,
        "fee_bps_per_side": 10.0,
        "slippage_bps_per_side": 5.0,
        "gross_realized_r": 0.0,
        "estimated_costs_r": (
            (10.0 + 5.0) / 10000.0 * entry / risk
        ),
        "realized_r": -((10.0 + 5.0) / 10000.0 * entry / risk),
        "events": [],
    }


def advance_lifecycle(
    side: str,
    plan: dict,
    lifecycle: dict | None,
    candle_high: float,
    candle_low: float,
    candle_timestamp: str,
) -> tuple[dict, bool]:
    """Advance at most one target tranche per closed candle.

    A stop and the next target touched in the same candle resolve to the stop;
    OHLC does not reveal intrabar order. TP1 moves the remaining stop to entry;
    TP2 moves it to TP1. The final 20% exits at TP3.
    """
    state = lifecycle or build_lifecycle(side, plan)
    if state.get("mode") != "PAPER_PRICE_TRACKING":
        return state, False
    if state.get("last_candle_timestamp") == candle_timestamp:
        return state, False

    entry = float(plan["entry"])
    risk = abs(entry - float(plan["stop_loss"]))
    direction = 1.0 if side == "BUY" else -1.0
    remaining = float(state["remaining_position_pct"])
    if remaining <= 0:
        return state, False

    stop = float(state["current_stop"])
    index = int(state["next_target_index"])
    target = float(state["targets"][index])
    stop_hit = candle_low <= stop if side == "BUY" else candle_high >= stop
    target_hit = candle_high >= target if side == "BUY" else candle_low <= target

    if not stop_hit and not target_hit:
        state["last_candle_timestamp"] = candle_timestamp
        return state, False

    ambiguous = stop_hit and target_hit
    if stop_hit:
        exit_price = stop
        gross_pnl_r = direction * (exit_price - entry) / risk * remaining / 100.0
        exit_cost_r = (
            (float(state["fee_bps_per_side"]) + float(state["slippage_bps_per_side"]))
            / 10000.0 * exit_price * remaining / 100.0 / risk
        )
        state["gross_realized_r"] = round(
            float(state["gross_realized_r"]) + gross_pnl_r, 8
        )
        state["estimated_costs_r"] = round(
            float(state["estimated_costs_r"]) + exit_cost_r, 8
        )
        state["realized_r"] = round(
            float(state["gross_realized_r"]) - float(state["estimated_costs_r"]), 8
        )
        pnl_r = gross_pnl_r - exit_cost_r
        state["closed_position_pct"] = round(
            float(state["closed_position_pct"]) + remaining, 8
        )
        state["remaining_position_pct"] = 0.0
        state["events"].append({
            "type": "STOP_EXIT",
            "price": exit_price,
            "position_pct": remaining,
            "realized_r": round(pnl_r, 8),
            "candle_timestamp": candle_timestamp,
            "ambiguous_candle": ambiguous,
            "reason": (
                "Stop diprioritaskan karena stop dan target tersentuh pada "
                "candle yang sama; urutan intrabar tidak tersedia."
                if ambiguous else "Stop tersentuh."
            ),
        })
        state["outcome"] = (
            "WIN" if state["realized_r"] > 1e-9
            else "LOSS" if state["realized_r"] < -1e-9
            else "BREAKEVEN"
        )
        state["closed"] = True
    else:
        allocation = float(state["target_allocations_pct"][index])
        tranche = min(allocation, remaining)
        gross_pnl_r = direction * (target - entry) / risk * tranche / 100.0
        exit_cost_r = (
            (float(state["fee_bps_per_side"]) + float(state["slippage_bps_per_side"]))
            / 10000.0 * target * tranche / 100.0 / risk
        )
        state["gross_realized_r"] = round(
            float(state["gross_realized_r"]) + gross_pnl_r, 8
        )
        state["estimated_costs_r"] = round(
            float(state["estimated_costs_r"]) + exit_cost_r, 8
        )
        state["realized_r"] = round(
            float(state["gross_realized_r"]) - float(state["estimated_costs_r"]), 8
        )
        pnl_r = gross_pnl_r - exit_cost_r
        state["remaining_position_pct"] = round(remaining - tranche, 8)
        state["closed_position_pct"] = round(
            float(state["closed_position_pct"]) + tranche, 8
        )
        state["events"].append({
            "type": f"TP{index + 1}",
            "price": target,
            "position_pct": tranche,
            "realized_r": round(pnl_r, 8),
            "candle_timestamp": candle_timestamp,
            "ambiguous_candle": False,
            "reason": f"TP{index + 1} tersentuh; partial close paper {tranche:.0f}%.",
        })
        state["next_target_index"] = index + 1
        if index == 0:
            state["current_stop"] = entry
        elif index == 1:
            state["current_stop"] = float(state["targets"][0])
        if state["remaining_position_pct"] <= 1e-9:
            state["remaining_position_pct"] = 0.0
            state["outcome"] = (
                "WIN" if state["realized_r"] > 1e-9
                else "LOSS" if state["realized_r"] < -1e-9
                else "BREAKEVEN"
            )
            state["closed"] = True
        else:
            # Once a target tranche is confirmed, also honor the newly tightened
            # stop if the same candle retraced through it. The previous stop was
            # checked first, so an original SL collision never earns TP credit.
            tightened_stop = float(state["current_stop"])
            tightened_stop_hit = (
                candle_low <= tightened_stop if side == "BUY"
                else candle_high >= tightened_stop
            )
            if tightened_stop_hit:
                remaining = float(state["remaining_position_pct"])
                gross_stop_r = (
                    direction * (tightened_stop - entry) / risk * remaining / 100.0
                )
                exit_cost_r = (
                    (float(state["fee_bps_per_side"]) + float(state["slippage_bps_per_side"]))
                    / 10000.0 * tightened_stop * remaining / 100.0 / risk
                )
                state["gross_realized_r"] = round(
                    float(state["gross_realized_r"]) + gross_stop_r, 8
                )
                state["estimated_costs_r"] = round(
                    float(state["estimated_costs_r"]) + exit_cost_r, 8
                )
                state["realized_r"] = round(
                    float(state["gross_realized_r"])
                    - float(state["estimated_costs_r"]), 8
                )
                stop_r = gross_stop_r - exit_cost_r
                state["closed_position_pct"] = round(
                    float(state["closed_position_pct"]) + remaining, 8
                )
                state["remaining_position_pct"] = 0.0
                state["events"].append({
                    "type": "TIGHTENED_STOP_EXIT",
                    "price": tightened_stop,
                    "position_pct": remaining,
                    "realized_r": round(stop_r, 8),
                    "candle_timestamp": candle_timestamp,
                    "ambiguous_candle": True,
                    "reason": (
                        "Setelah partial TP, stop yang diperketat ikut tersentuh "
                        "dalam candle yang sama; sisa posisi ditutup pada stop baru."
                    ),
                })
                state["ambiguous_candle"] = True
                state["outcome"] = (
                    "WIN" if state["realized_r"] > 1e-9
                    else "LOSS" if state["realized_r"] < -1e-9
                    else "BREAKEVEN"
                )
                state["closed"] = True

    state["last_candle_timestamp"] = candle_timestamp
    state["ambiguous_candle"] = bool(state.get("ambiguous_candle")) or ambiguous
    return state, True
