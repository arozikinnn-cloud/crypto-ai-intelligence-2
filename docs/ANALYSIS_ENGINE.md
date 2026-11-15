# Analysis engine

The API is research-only. It does not place exchange orders and does not promise profitability.

## Technical analysis

The technical engine computes EMA20/EMA50, RSI14, MACD, ATR14, volume ratio, rolling support/resistance, and deterministic BUY/SELL/NO TRADE evidence. The confluence score is not a calibrated probability or win rate.

## Structure and SMC

Structure analysis uses confirmed swing pivots, BOS/CHOCH, wick-based liquidity sweep heuristics, three-candle FVGs, and last-opposing-candle order-block zones. These are price-action heuristics, not evidence of actual resting institutional orders.

## Order flow and CVD scope

- `/api/v1/analysis/order-flow` estimates aggressor delta from Binance Spot kline taker-buy volume.
- `/api/v1/analysis/order-flow/aggtrades` derives buyer/seller aggressor volume from Binance Spot aggregated trades.
- The aggTrades endpoint returns a 1-minute bucketed curve for its recent response batch. It does not write that partial REST batch into persistent CVD history; the background collector is the persistent source.
- A background Spot `@aggTrade` collector starts with the API by default, batches writes, reconnects with exponential backoff, and deduplicates using Binance aggregate-trade IDs.
- `/api/v1/analysis/order-flow/cvd-history` reads the stored 1-minute CVD history. Configure `CVD_COLLECTOR_ENABLED`, `CVD_COLLECTOR_SYMBOLS`, and `CVD_COLLECTOR_FLUSH_INTERVAL_SECONDS`.
- `GET /api/v1/analysis/order-book` reports bid/ask notional imbalance and spread from a live depth snapshot. It is not a time-series DOM feed and cannot establish absorption or spoofing.
- The combined `/api/v1/analysis/intelligence` endpoint includes persistent CVD history, observed liquidation context, and order-book imbalance when available. Historical CVD/order-book context is an additional confluence check; liquidation totals remain contextual rather than directional.
- Persistent CVD is observed history, not guaranteed complete session history: downtime, network loss, database outages, and exchange stream gaps can leave missing intervals. It begins collecting only after the collector is running.
- Binance aggTrades is trade-level aggregated data, not raw individual fills, order-book depth, DOM, footprint, or absorption.

## Derivatives and liquidations

Open interest and funding are contextual metrics, not standalone directional signals. A background USD-M Futures `@forceOrder` collector starts by default for configured symbols, reconnects with backoff, and stores deduplicated events. `/api/v1/analysis/liquidations/history` aggregates observed liquidation events by minute and side (BUY=short liquidations; SELL=long liquidations). Configure `LIQUIDATION_COLLECTOR_ENABLED`, `LIQUIDATION_COLLECTOR_SYMBOLS`, and `LIQUIDATION_COLLECTOR_FLUSH_INTERVAL_SECONDS`. Binance force-order streams are rate-limited/partial feeds, not a complete market-wide liquidation tape or heatmap; downtime and source limitations can leave gaps.

## Combined intelligence backtest and quality validation

- `GET /api/v1/analysis/intelligence/backtest` replays closed-candle decisions using technical indicators, structure heuristics, and kline order flow. It enters at the next candle open and exits at a configurable fixed candle horizon.
- The response separates train and out-of-sample metrics: trade count, win rate, total return, expectancy, profit factor, and maximum drawdown. It also reports explicit quality gates and known limitations.
- Estimated fee and slippage are configurable in basis points per side. The simulation allows only one open position at a time, excludes trades crossing the train/test boundary, and rejects candle series with gaps or irregular intervals.
- Historical aggTrades/CVD, liquidation events, order-book depth, OI/funding, news, and sentiment are not replayed in this version. Therefore this is not a full historical replay of every live intelligence input.
- `GET /api/v1/analysis/intelligence/timeframe-performance` compares the same rule set across selected timeframes. It uses equal candle counts and equal candle-horizon settings, not equal calendar durations; compare trade count and out-of-sample metrics before drawing conclusions.
- The older `/api/v1/analysis/backtest` remains an EMA20/EMA50 baseline and should not be confused with the combined-intelligence backtest.

## Signal lifecycle and notifications

- Every live combined-intelligence request records BUY/SELL signal events in the database. Repeated same-side requests refresh the active event rather than creating duplicate alerts.
- An opposite signal invalidates the previous active side; a NO TRADE decision invalidates active signals for the same symbol/timeframe set.
- `GET /api/v1/signals` lists active, closed, invalidated, or all events. `POST /api/v1/signals/{signal_id}/close` closes an event.
- `GET /api/v1/signals/notifications?unread_only=true` polls the in-app notification inbox; `POST /api/v1/signals/notifications/{notification_id}/read` marks an alert as read.
- This backend inbox is not Android push delivery. Firebase Cloud Messaging, device-token registration, user preferences, and a mobile notification UI still need to be implemented before alerts can arrive while the app is closed.

Transient Binance HTTP/network failures use bounded retries with exponential backoff; persistent failure still returns a controlled market-data error. WebSocket collectors reconnect with bounded exponential backoff.

The combined engine remains deterministic and rule-based, not a trained probability model. Backtests are research evidence only, not a guarantee of future performance.
