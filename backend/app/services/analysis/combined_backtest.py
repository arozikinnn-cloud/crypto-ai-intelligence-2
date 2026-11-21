from app.services.analysis.backtest import run_strategy_backtest
from app.services.market_data.base import NormalizedCandle


def run_combined_backtest(
    candles: list[NormalizedCandle],
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    horizon: int = 3,
    train_ratio: float = 0.7,
) -> dict:
    if not 1 <= horizon <= 24:
        raise ValueError("Horizon must be between 1 and 24 candles.")
    result = run_strategy_backtest(
        candles,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        train_ratio=train_ratio,
        max_holding_candles=horizon,
    )
    return {
        "symbol": result["symbol"],
        "timeframe": result["timeframe"],
        "candles": result["candles"],
        "strategy": result["strategy"],
        "execution": (
            "Signal on closed candle; entry at next candle open; ATR-based stop "
            "and 1:1.5 target; exit at first barrier or horizon close."
        ),
        "horizon_candles": horizon,
        "fee_bps_per_side": fee_bps,
        "slippage_bps_per_side": slippage_bps,
        "train": result["train"],
        "out_of_sample": result["out_of_sample"],
        "overall": result["overall"],
        "signal_count": result["signal_count"],
        "no_trade_count": result["no_trade_count"],
        "quality_checks": result["quality_checks"],
        "limitations": [
            "This is a single-timeframe replay of RSI16, MA40 and Ichimoku; "
            "it is not a complete H1/M15/M5 synchronized replay.",
            "Historical aggTrades/CVD, order book, OI, funding and liquidation "
            "events are not replayed.",
            "If TP and SL are touched in the same candle, the result is counted "
            "as SL conservatively because OHLC cannot reveal intrabar order.",
            "Partial tranches are simulated as paper fills; actual exchange partial "
            "fills, spread variation and market impact are not modeled. "
            "Fees and slippage are estimates.",
            "A deterministic technical heuristic is not a trained probability model "
            "and does not guarantee future performance.",
        ],
    }
