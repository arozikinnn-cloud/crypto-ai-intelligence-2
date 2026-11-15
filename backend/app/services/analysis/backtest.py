from app.services.analysis.indicators import _ema
from app.services.market_data.base import NormalizedCandle


def _metrics(returns: list[float]) -> dict:
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    positive = 0.0
    negative = 0.0
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
        "win_rate_pct": (wins / len(returns) * 100) if returns else 0.0,
        "total_return_pct": (equity - 1) * 100,
        "profit_factor": positive / negative if negative else None,
        "max_drawdown_pct": max_drawdown * 100,
    }


def _segment_returns(
    candles: list[NormalizedCandle],
    signals: list[int | None],
    start: int,
    end: int,
    fee_bps: float,
    slippage_bps: float,
) -> list[float]:
    fee = fee_bps / 10000
    slippage = slippage_bps / 10000
    position = 0
    entry_price = 0.0
    returns = []

    for signal_index in range(max(start, 49), end - 1):
        signal = signals[signal_index]
        if signal is None or signal == position:
            continue
        execution_open = candles[signal_index + 1].open
        if position:
            exit_price = execution_open * (1 - slippage * position)
            gross_return = position * (exit_price - entry_price) / entry_price
            returns.append(gross_return - 2 * fee)
        position = signal
        entry_price = execution_open * (1 + slippage * position)

    if position and end > start:
        exit_price = candles[end - 1].close * (1 - slippage * position)
        gross_return = position * (exit_price - entry_price) / entry_price
        returns.append(gross_return - 2 * fee)
    return returns


def run_ema_backtest(
    candles: list[NormalizedCandle],
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    train_ratio: float = 0.7,
) -> dict:
    if len(candles) < 120:
        raise ValueError("At least 120 candles are required for an out-of-sample backtest.")
    if not 0 <= fee_bps <= 100 or not 0 <= slippage_bps <= 100:
        raise ValueError("Fee and slippage must be between 0 and 100 basis points.")
    if not 0.5 <= train_ratio <= 0.9:
        raise ValueError("Train ratio must be between 0.5 and 0.9.")

    closes = [candle.close for candle in candles]
    fast = _ema(closes, 20)
    slow = _ema(closes, 50)
    fast_aligned = [None] * 19 + fast
    slow_aligned = [None] * 49 + slow
    signals = [
        (1 if fast_value > slow_value else -1)
        if fast_value is not None and slow_value is not None else None
        for fast_value, slow_value in zip(fast_aligned, slow_aligned)
    ]

    split = int(len(candles) * train_ratio)
    train_returns = _segment_returns(candles, signals, 0, split, fee_bps, slippage_bps)
    test_returns = _segment_returns(candles, signals, split, len(candles), fee_bps, slippage_bps)
    return {
        "symbol": candles[-1].symbol,
        "timeframe": candles[-1].timeframe,
        "candles": len(candles),
        "train_ratio": train_ratio,
        "fee_bps_per_side": fee_bps,
        "slippage_bps_per_side": slippage_bps,
        "strategy": "EMA20/EMA50 crossover, long/short simulation",
        "train": _metrics(train_returns),
        "out_of_sample": _metrics(test_returns),
        "warning": (
            "Historical simulation only. Includes estimated fees and slippage; "
            "does not guarantee future performance or model real execution."
        ),
    }
