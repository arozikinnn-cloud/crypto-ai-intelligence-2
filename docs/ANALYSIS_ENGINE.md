# Analysis engine

The API is research-only. It does not place exchange orders and does not promise profitability.

## Technical analysis

The technical engine computes EMA20/EMA50, RSI14, MACD, ATR14, volume ratio, rolling support/resistance, and deterministic BUY/SELL/NO TRADE evidence. The confluence score is not a calibrated probability or win rate.

## Structure and SMC

Structure analysis uses confirmed swing pivots, BOS/CHOCH, wick-based liquidity sweep heuristics, three-candle FVGs, and last-opposing-candle order-block zones. These are price-action heuristics, not evidence of actual resting institutional orders.

## Order flow and CVD scope

- `/api/v1/analysis/order-flow` estimates aggressor delta from Binance Spot kline taker-buy volume.
- `/api/v1/analysis/order-flow/aggtrades` derives buyer/seller aggressor volume from Binance Spot aggregated trades.
- The aggTrades endpoint returns a 1-minute bucketed CVD curve and persists observed buckets in the local database.
- A background Spot `@aggTrade` collector starts with the API by default, batches writes, reconnects with exponential backoff, and deduplicates using Binance aggregate-trade IDs.
- `/api/v1/analysis/order-flow/cvd-history` reads the stored 1-minute CVD history. Configure `CVD_COLLECTOR_ENABLED`, `CVD_COLLECTOR_SYMBOLS`, and `CVD_COLLECTOR_FLUSH_INTERVAL_SECONDS`.
- Persistent CVD is observed history, not guaranteed complete session history: downtime, network loss, database outages, and exchange stream gaps can leave missing intervals. It begins collecting only after the collector is running.
- Binance aggTrades is trade-level aggregated data, not raw individual fills, order-book depth, DOM, footprint, or absorption.

## Derivatives and liquidations

Open interest and funding are contextual metrics, not standalone directional signals. A background USD-M Futures `@forceOrder` collector starts by default for configured symbols, reconnects with backoff, and stores deduplicated events. `/api/v1/analysis/liquidations/history` aggregates observed liquidation events by minute and side (BUY=short liquidations; SELL=long liquidations). Configure `LIQUIDATION_COLLECTOR_ENABLED`, `LIQUIDATION_COLLECTOR_SYMBOLS`, and `LIQUIDATION_COLLECTOR_FLUSH_INTERVAL_SECONDS`. Binance force-order streams are rate-limited/partial feeds, not a complete market-wide liquidation tape or heatmap; downtime and source limitations can leave gaps.

## Backtesting limitations

The current EMA crossover backtest is a separate baseline strategy and does not validate the combined intelligence decision. It uses estimated fees/slippage and a chronological in/out-of-sample split. Historical results do not guarantee future performance.
