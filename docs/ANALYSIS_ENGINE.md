# Analysis engine

The API is research-only. It does not place exchange orders and does not promise profitability.

## Technical analysis

The technical engine computes EMA20/EMA50, RSI14, MACD, ATR14, volume ratio, rolling support/resistance, and deterministic BUY/SELL/NO TRADE evidence. The confluence score is not a calibrated probability or win rate.

## Structure and SMC

Structure analysis uses confirmed swing pivots, BOS/CHOCH, wick-based liquidity sweep heuristics, three-candle FVGs, and last-opposing-candle order-block zones. These are price-action heuristics, not evidence of actual resting institutional orders.

## Order flow and CVD scope

- `/api/v1/analysis/order-flow` estimates aggressor delta from Binance Spot kline taker-buy volume.
- `/api/v1/analysis/order-flow/aggtrades` derives buyer/seller aggressor volume from Binance Spot aggregated trades.
- The aggTrades endpoint returns a 1-minute bucketed CVD curve (`cvd_points`) and terminal CVD for the returned batch.
- `cvd_scope=returned_batch_only` is intentional: the public endpoint returns a bounded recent batch. This is not persistent session CVD or an all-day cumulative series.
- Binance aggTrades is trade-level aggregated data, not raw individual fills, order-book depth, DOM, footprint, or absorption.

## Derivatives and liquidations

Open interest and funding are contextual metrics, not standalone directional signals. The Futures force-order WebSocket is an event pass-through; it is not a complete liquidation heatmap or a durable liquidation database.

## Backtesting limitations

The current EMA crossover backtest is a separate baseline strategy and does not validate the combined intelligence decision. It uses estimated fees/slippage and a chronological in/out-of-sample split. Historical results do not guarantee future performance.
