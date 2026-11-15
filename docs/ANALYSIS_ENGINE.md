# Phase 3 — Technical analysis engine

## Scope
The engine consumes normalized Binance Spot OHLCV candles and returns an explainable research-only assessment. It does not place orders and does not claim predictive certainty.

## Features
- EMA 20 and EMA 50 trend alignment.
- RSI 14 momentum.
- MACD (12, 26, 9) line and signal comparison.
- ATR 14 volatility estimate.
- Current volume relative to the previous 20-candle average.
- Rolling 20-candle support and resistance bounds.

## Rule-based assessment
BUY requires at least three of four bullish checks: bullish EMA alignment, RSI 50–70, MACD above its signal, and volume ratio >= 1. SELL uses mirrored bearish checks. Otherwise the result is NO TRADE. This is deliberately conservative and transparent.

The confluence score is a count of satisfied rule checks, not a calibrated probability, expected return, or guarantee. Entry is the latest candle close. Stop distance is 1.5 ATR and target is 2R by default. These levels are analytical references, not exchange orders.

## API
- GET /api/v1/analysis/technical?symbol=BTCUSDT&interval=1h&limit=200
- GET /api/v1/analysis/backtest?symbol=BTCUSDT&interval=1h&limit=500&fee_bps=10&slippage_bps=5

The technical endpoint requires at least 60 candles. Backtesting requires at least 120 candles and reports separate 70% in-sample and 30% out-of-sample metrics. The EMA20/EMA50 crossover simulation uses next-candle open execution and deducts estimated fees and slippage on entry and exit. Default cost assumptions are 10 basis points fee and 5 basis points slippage per side; users can override them within bounded API limits.

## Limitations
This is an initial technical baseline. It does not yet include SMC/order-flow/liquidation/open-interest/fundamental/sentiment analysis, multi-timeframe confluence, walk-forward optimization, or model calibration. The backtest is a simplified long/short simulation, not a broker/exchange fill model. Do not treat its results as financial advice or a forecast.
