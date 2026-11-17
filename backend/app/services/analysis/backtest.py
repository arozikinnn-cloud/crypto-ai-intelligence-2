from math import isfinite

from app.services.analysis.engine import analyze_market
from app.services.market_data.base import NormalizedCandle
from app.services.market_data.quality import validate_candles, validate_candle_continuity


def _metrics(returns: list[float]) -> dict:
    equity = peak = 1.0
    max_drawdown = positive = negative = 0.0
    wins = 0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
        if value > 0:
            wins += 1
            positive += value
        elif value < 0:
            negative += abs(value)
    return {
        "trades": len(returns),
        "win_rate_pct": wins / len(returns) * 100 if returns else 0.0,
        "total_return_pct": (equity - 1) * 100,
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
        target = (
            entry + risk_distance * 1.5
            if side == "BUY"
            else entry - risk_distance * 1.5
        )
        last_index = min(len(candles) - 1, entry_index + max_holding_candles - 1)
        exit_index = last_index
        exit_price = candles[last_index].close
        outcome = "TIME_EXIT"

        for index in range(entry_index, last_index + 1):
            candle = candles[index]
            hit_stop = (
                candle.low <= stop if side == "BUY" else candle.high >= stop
            )
            hit_target = (
                candle.high >= target if side == "BUY" else candle.low <= target
            )
            if hit_stop and hit_target:
                # OHLC cannot prove intrabar order; resolve ambiguity as a loss.
                exit_index, exit_price, outcome = index, stop, "SL_AMBIGUOUS"
                break
            if hit_stop:
                exit_index, exit_price, outcome = index, stop, "SL"
                break
            if hit_target:
                exit_index, exit_price, outcome = index, target, "TP"
                break

        executed_entry = entry * (1 + slippage * direction)
        executed_exit = exit_price * (1 - slippage * direction)
        net_return = (
            direction * (executed_exit - executed_entry) / executed_entry - 2 * fee
        )
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
        "strategy": "RSI16 + MA40 + Ichimoku Kumo; ATR stop; fixed 1:1.5 risk/reward",
        "train": _metrics(train),
        "out_of_sample": _metrics(test),
        "warning": (
            "Historical single-timeframe replay of the current technical engine. "
            "This is not a full H1/M15/M5 multi-timeframe replay and does not replay "
            "historical aggTrades/CVD, order book, OI, funding or liquidation data. "
            "TP and SL hit in the same candle are counted as SL conservatively. "
            "Fees and slippage are estimates; results do not guarantee future performance."
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
