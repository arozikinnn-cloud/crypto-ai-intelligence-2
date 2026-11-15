from math import isfinite

from app.services.analysis.engine import analyze_market
from app.services.analysis.intelligence import build_intelligence_decision
from app.services.analysis.order_flow import analyze_order_flow
from app.services.analysis.structure import analyze_structure
from app.services.market_data.base import MarketDataError, NormalizedCandle
from app.services.market_data.quality import validate_candles, validate_candle_continuity


def _stats(returns: list[float]) -> dict:
    equity = peak = 1.0
    max_drawdown = 0.0
    wins = losses_count = flats = 0
    gains = losses = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak)
        if value > 0:
            wins += 1
            gains += value
        elif value < 0:
            losses_count += 1
            losses += abs(value)
        else:
            flats += 1
    count = len(returns)
    return {
        "trades": count,
        "wins": wins,
        "losses": losses_count,
        "flats": flats,
        "win_rate_pct": wins / count * 100 if count else 0.0,
        "total_return_pct": (equity - 1) * 100,
        "expectancy_pct": sum(returns) / count * 100 if count else 0.0,
        "profit_factor": gains / losses if losses else None,
        "max_drawdown_pct": max_drawdown * 100,
    }


def run_combined_backtest(
    candles: list[NormalizedCandle],
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    horizon: int = 3,
    train_ratio: float = 0.7,
) -> dict:
    if len(candles) < 140:
        raise ValueError("At least 140 closed candles are required.")
    if not 0 <= fee_bps <= 100 or not 0 <= slippage_bps <= 100:
        raise ValueError("Fee and slippage must be between 0 and 100 bps per side.")
    if not 1 <= horizon <= 24:
        raise ValueError("Horizon must be between 1 and 24 candles.")
    if not 0.5 <= train_ratio <= 0.9:
        raise ValueError("Train ratio must be between 0.5 and 0.9.")
    validate_candles(candles)
    if any(
        candle.symbol != candles[0].symbol
        or candle.timeframe != candles[0].timeframe
        for candle in candles
    ):
        raise MarketDataError("Backtest candles must use one symbol and timeframe.")
    validate_candle_continuity(candles)

    split = int(len(candles) * train_ratio)
    observations = []
    next_available_index = 120
    # One position at a time; signals are evaluated only after the prior position exits.
    for index in range(120, len(candles) - horizon):
        if index < next_available_index:
            continue
        history = candles[: index + 1]
        try:
            technical = analyze_market(history)
            structure = analyze_structure(history)
            flow = analyze_order_flow(history, lookback=min(20, len(history)))
            decision = build_intelligence_decision(
                [technical["side"]], structure, flow, {}, None
            )
        except (ValueError, KeyError):
            continue
        side = decision["side"]
        if side not in {"BUY", "SELL"}:
            continue
        entry = candles[index + 1].open
        exit_price = candles[index + horizon].close
        if (
            entry <= 0
            or exit_price <= 0
            or not isfinite(entry)
            or not isfinite(exit_price)
        ):
            continue
        direction = 1 if side == "BUY" else -1
        slip = slippage_bps / 10000
        fee = fee_bps / 10000
        executed_entry = entry * (1 + slip * direction)
        executed_exit = exit_price * (1 - slip * direction)
        result = direction * (executed_exit - executed_entry) / executed_entry - 2 * fee
        observations.append({"index": index, "side": side, "return": result})
        next_available_index = index + horizon

    train = [x["return"] for x in observations if x["index"] + horizon < split]
    test = [x["return"] for x in observations if x["index"] >= split]
    all_returns = [x["return"] for x in observations]
    return {
        "symbol": candles[-1].symbol,
        "timeframe": candles[-1].timeframe,
        "candles": len(candles),
        "strategy": "Rolling technical + structure + kline order-flow confluence",
        "execution": "Next candle open; fixed holding horizon; close at horizon candle close",
        "horizon_candles": horizon,
        "fee_bps_per_side": fee_bps,
        "slippage_bps_per_side": slippage_bps,
        "train": _stats(train),
        "out_of_sample": _stats(test),
        "overall": _stats(all_returns),
        "signal_count": len(observations),
        "no_trade_count": max(
            0, len(candles) - horizon - 120 - len(observations)
        ),
        "quality_checks": {
            "minimum_oos_trades_met": len(test) >= 30,
            "positive_oos_expectancy": bool(test) and sum(test) / len(test) > 0,
            "oos_drawdown_below_20pct": _stats(test)["max_drawdown_pct"] < 20,
        },
        "limitations": [
            "AggTrades/CVD and liquidation history are not replayed historically; "
            "this backtest uses technical, structure and kline order-flow only.",
            "The current signal rules are deterministic heuristics, "
            "not a trained probability model.",
            "No funding, spread variation, market impact, partial fills, "
            "or intrabar stop/target simulation.",
            "Signals are evaluated on closed candles; entry is next candle open "
            "and exit uses a fixed horizon.",
        ],
    }
