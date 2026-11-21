from math import isfinite

from app.services.analysis.engine import analyze_market
from app.services.market_data.base import NormalizedCandle
from app.services.market_data.quality import validate_candles, validate_candle_continuity


def _metrics(returns: list[float]) -> dict:
    equity = peak = 1.0
    max_drawdown = positive = negative = 0.0
    wins = losses = flats = 0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
        if value > 0:
            wins += 1
            positive += value
        elif value < 0:
            losses += 1
            negative += abs(value)
        else:
            flats += 1
    count = len(returns)
    return {
        "trades": count,
        "wins": wins,
        "losses": losses,
        "flats": flats,
        "win_rate_pct": wins / count * 100 if count else 0.0,
        "total_return_pct": (equity - 1) * 100,
        "expectancy_pct": sum(returns) / count * 100 if count else 0.0,
        "profit_factor": positive / negative if negative else None,
        "max_drawdown_pct": max_drawdown * 100,
    }


def run_strategy_backtest(
    candles: list[NormalizedCandle],
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    train_ratio: float = 0.7,
    max_holding_candles: int = 24,
) -> dict:
    if len(candles) < 140:
        raise ValueError("At least 140 closed candles are required for the strategy backtest.")
    if not 0 <= fee_bps <= 100 or not 0 <= slippage_bps <= 100:
        raise ValueError("Fee and slippage must be between 0 and 100 basis points.")
    if not 0.5 <= train_ratio <= 0.9:
        raise ValueError("Train ratio must be between 0.5 and 0.9.")
    if not 1 <= max_holding_candles <= 100:
        raise ValueError("Maximum holding period must be between 1 and 100 candles.")

    validate_candles(candles)
    validate_candle_continuity(candles)
    if any(
        candle.symbol != candles[0].symbol
        or candle.timeframe != candles[0].timeframe
        for candle in candles
    ):
        raise ValueError("Backtest candles must use one symbol and timeframe.")

    split = int(len(candles) * train_ratio)
    fee = fee_bps / 10000
    slippage = slippage_bps / 10000
    trades: list[dict] = []
    next_available_index = 80

    # Each signal uses only candles closed up to that point. Entry is the next open.
    for signal_index in range(79, len(candles) - 1):
        if signal_index < next_available_index:
            continue
        history = candles[:signal_index + 1]
        try:
            signal = analyze_market(history)
        except ValueError:
            continue
        side = signal["side"]
        if side not in {"BUY", "SELL"}:
            continue

        signal_close = candles[signal_index].close
        signal_stop = signal.get("stop_loss")
        if not isinstance(signal_stop, (int, float)):
            continue
        risk_distance = abs(signal_close - float(signal_stop))
        entry_index = signal_index + 1
        entry = candles[entry_index].open
        if (
            risk_distance <= 0 or entry <= 0
            or not isfinite(risk_distance) or not isfinite(entry)
        ):
            continue

        direction = 1 if side == "BUY" else -1
        stop = entry - risk_distance if side == "BUY" else entry + risk_distance
        last_index = min(len(candles) - 1, entry_index + max_holding_candles - 1)
        exit_index = last_index
        remaining_pct = 100.0
        realized_r = 0.0
        current_stop = stop
        target_prices = [
            entry + direction * risk_distance,
            entry + direction * risk_distance * 2,
            entry + direction * risk_distance * 3,
        ]
        allocations = [50.0, 30.0, 20.0]
        target_index = 0
        outcome = "TIME_EXIT"

        for index in range(entry_index, last_index + 1):
            candle = candles[index]
            next_target = target_prices[target_index]
            hit_stop = (
                candle.low <= current_stop if side == "BUY"
                else candle.high >= current_stop
            )
            hit_target = (
                candle.high >= next_target if side == "BUY"
                else candle.low <= next_target
            )
            if hit_stop:
                # A same-candle stop/target collision resolves to the stop.
                realized_r += (
                    direction * (current_stop - entry) / risk_distance
                    * remaining_pct / 100.0
                )
                exit_index = index
                outcome = (
                    "SL_AMBIGUOUS" if hit_target else
                    "SL_AFTER_TP2" if target_index == 2 else
                    "SL_AFTER_TP1" if target_index == 1 else "SL"
                )
                remaining_pct = 0.0
                break
            if hit_target:
                tranche = min(allocations[target_index], remaining_pct)
                realized_r += (
                    direction * (next_target - entry) / risk_distance
                    * tranche / 100.0
                )
                remaining_pct -= tranche
                exit_index = index
                if target_index == 0:
                    current_stop = entry
                    outcome = "TP1_PARTIAL"
                elif target_index == 1:
                    current_stop = target_prices[0]
                    outcome = "TP2_PARTIAL"
                else:
                    outcome = "TP3"
                target_index += 1
                if remaining_pct <= 1e-9:
                    remaining_pct = 0.0
                    break
                # At most one tranche is credited per candle to avoid inventing
                # an intrabar path when several targets lie inside one OHLC bar.

        if remaining_pct > 0:
            # Any unclosed tranche is marked at the actual horizon candle close.
            exit_index = last_index
            time_exit_price = candles[last_index].close
            realized_r += (
                direction * (time_exit_price - entry) / risk_distance
                * remaining_pct / 100.0
            )
            if outcome != "TIME_EXIT":
                outcome = f"{outcome}_REMAINDER_TIME_EXIT"

        # Fees and slippage are charged on the full entry and aggregate exit
        # notional. This is a conservative estimate, not exchange fill data.
        net_return = realized_r * risk_distance / entry - 2 * fee - 2 * slippage
        trades.append({
            "entry_index": entry_index,
            "exit_index": exit_index,
            "return": net_return,
            "outcome": outcome,
        })
        next_available_index = exit_index + 1

    # Trades crossing the train/test boundary are excluded from both samples.
    train = [
        item["return"] for item in trades if item["exit_index"] < split
    ]
    test = [
        item["return"] for item in trades if item["entry_index"] >= split
    ]
    return {
        "symbol": candles[-1].symbol,
        "timeframe": candles[-1].timeframe,
        "candles": len(candles),
        "train_ratio": train_ratio,
        "fee_bps_per_side": fee_bps,
        "slippage_bps_per_side": slippage_bps,
        "strategy": "RSI16 + MA40 + Ichimoku Kumo; ATR stop; 50/30/20 partial exits at 1R/2R/3R",
        "train": _metrics(train),
        "out_of_sample": _metrics(test),
        "overall": _metrics([item["return"] for item in trades]),
        "signal_count": len(trades),
        "no_trade_count": max(0, len(candles) - 80 - 1 - len(trades)),
        "quality_checks": {
            "minimum_oos_trades_met": len(test) >= 30,
            "positive_oos_expectancy": bool(test) and sum(test) / len(test) > 0,
            "oos_drawdown_below_20pct": _metrics(test)["max_drawdown_pct"] < 20,
        },
        "warning": (
            "Historical single-timeframe replay of the current technical engine. "
            "This is not a full H1/M15/M5 multi-timeframe replay and does not replay "
            "historical aggTrades/CVD, order book, OI, funding or liquidation data. "
            "TP and SL hit in the same candle are counted as SL conservatively. "
            "Partial exits are modeled at 50%/30%/20% at 1R/2R/3R; the stop moves to breakeven after TP1 and TP1 after TP2. Fees and slippage are estimates; results do not guarantee future performance."
        ),
    }


# Backward-compatible import for existing integrations; the strategy is no longer EMA-based.
def run_ema_backtest(
    candles: list[NormalizedCandle],
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    train_ratio: float = 0.7,
) -> dict:
    return run_strategy_backtest(
        candles,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        train_ratio=train_ratio,
    )
