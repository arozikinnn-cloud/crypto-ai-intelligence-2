# Analysis engine

The API is research-only. It does not place exchange orders and does not promise profitability.

## Technical analysis

- `GET /api/v1/analysis/technical?symbol=BTCUSDT&interval=1h&limit=200`
- Uses EMA20/EMA50, RSI14, MACD, ATR14, volume ratio, rolling support/resistance, and a transparent four-check confluence rule.
- BUY/SELL requires at least three aligned checks. Otherwise the result is NO TRADE.
- Entry is the latest confirmed candle close; reference SL/TP are ATR-based. They are analytical references, not execution instructions.
- Analysis endpoints request closed candles only, avoiding signals based on a still-forming kline.

## Multi-timeframe analysis

- `GET /api/v1/analysis/multi-timeframe?symbol=BTCUSDT&intervals=15m,1h,4h&limit=200`
- Fetches up to four unique intervals concurrently.
- Overall BUY/SELL is returned only if every requested timeframe independently produces the same directional signal. Any disagreement or NO TRADE result produces overall NO TRADE.

## Market structure / SMC baseline

- `GET /api/v1/analysis/structure?symbol=BTCUSDT&interval=1h&limit=200`
- Reports confirmed swing pivots, basic BOS/CHOCH, and the latest simple three-candle bullish/bearish fair-value gap.
- Pivots require two candles on the right to confirm. FVG is a geometric gap only; it does not prove an unmitigated or tradeable imbalance. This is not a full institutional SMC implementation.

## Order-flow proxy

- `GET /api/v1/analysis/order-flow?symbol=BTCUSDT&interval=5m&lookback=20`
- Binance Spot kline taker-buy base volume is used as the buy-aggressor estimate. Sell-aggressor volume is estimated as total base volume minus taker-buy volume.
- Per-candle delta is buy estimate minus sell estimate. The response's `cumulative_delta` is the sum of those deltas only across the selected lookback window.
- The response is a kline-derived proxy, not DOM, footprint, tick-by-tick CVD, absorption, or liquidation data. It must not be described as those measures.

## Futures derivatives context

- `GET /api/v1/analysis/derivatives?symbol=BTCUSDT&period=5m`
- Fetches public Binance USD-M Futures open-interest history and the latest funding-rate record.
- Open-interest change compares the last two available records in the selected period. OI rising does not identify whether new positions are long or short. Positive funding means longs pay shorts; negative funding means shorts pay longs.
- Derivatives context is separate from the spot order-flow proxy. Do not combine these into a directional signal without additional validation.

## Backtest

- `GET /api/v1/analysis/backtest?symbol=BTCUSDT&interval=1h&limit=500`
- EMA crossover historical simulation with estimated fees/slippage and an out-of-sample segment. Results are not a guarantee of future performance.

## Data handling and limitations

- Public Binance endpoints are used; no API key is required for these public reads.
- Analysis routes filter out the currently forming candle and use closed candles only.
- Exchange failures, malformed responses, insufficient history, and missing taker-buy data result in explicit errors rather than fabricated estimates.
- Current implementation does not include full order-book depth, DOM/footprint, absorption, liquidation heatmaps, long-running session CVD, calibrated ML probabilities, or signal notifications. The liquidation WebSocket is a live pass-through only and is not stored.


## Combined intelligence

- `GET /api/v1/analysis/intelligence?symbol=BTCUSDT&intervals=15m,1h,4h&limit=200&order_flow_interval=5m&derivatives_period=5m`
- Combines closed-candle technical analysis across selected timeframes, confirmed structure analysis, a bounded kline taker-volume delta window, open-interest change, and the latest funding rate.
- BUY or SELL is intentionally strict: all requested technical timeframes, structure, order-flow pressure, rising OI, and the funding filter must agree. Otherwise the combined result is NO TRADE.
- The five-point score is a count of heuristic checks, not a probability, confidence calibration, or expected win rate. Funding thresholds are provisional heuristics and require empirical validation.

## Live liquidation events

- WebSocket: `/api/v1/analysis/liquidations/stream?symbol=BTCUSDT`
- Proxies the Binance USD-M Futures symbol-specific `forceOrder` stream and normalizes liquidation side, price, quantity, notional, and event time.
- Binance force-order events are a real-time feed, not a complete historical liquidation tape or liquidation heatmap. BUY liquidation events correspond to short liquidations; SELL events correspond to long liquidations.
- The stream is client-driven and does not persist events. A client disconnect or upstream failure ends the stream; durable collection, aggregation, alerting, and heatmap construction remain future work.
