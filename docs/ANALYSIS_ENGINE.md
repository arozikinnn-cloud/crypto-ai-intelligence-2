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
GET /api/v1/analysis/technical?symbol=BTCUSDT&interval=1h&limit=200

At least 60 candles are required. Supported intervals are enforced by the market-data adapter. Public Binance access and rate limits apply.

## Limitations
This is an initial technical baseline. It does not yet include SMC/order-flow/liquidation/open-interest/fundamental/sentiment analysis, multi-timeframe confluence, walk-forward backtesting, or model calibration. Do not treat its output as financial advice.
