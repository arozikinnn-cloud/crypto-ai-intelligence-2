# Project roadmap

## Phase 1 — Foundation
Repository structure, FastAPI app, versioned API, configuration, logging, error handling, CORS baseline, SQLAlchemy session/model, health probes, tests, CI, architecture/API/database docs, and Flutter shell.

## Phase 2 — Market data
Public Binance Spot REST candle ingestion, normalized UTC OHLCV schema, candle quality validation, historical candle persistence/upsert, market-data API, and an opt-in reconnecting Binance WebSocket consumer. Provider credentials are not required for public market data.

## Phase 3 — Analysis engine
Initial explainable technical analysis API with EMA20/EMA50, RSI14, MACD, ATR14, volume ratio, rolling support/resistance, rule-based BUY/SELL/NO TRADE decisions, ATR-based reference SL/TP, and EMA crossover backtesting with fees, slippage, and a 70/30 in-sample/out-of-sample split. This is a technical baseline, not a calibrated AI probability model. Advanced SMC/order-flow/liquidation/open-interest/fundamental/sentiment and multi-timeframe confluence remain future extensions.

## Phase 4 — Signals and notifications
Signal lifecycle, deduplication, push notifications, user preferences, and alert audit trail.

## Phase 5 — App integration and hardening
Flutter dashboards, watchlists, signal details, authentication, rate limits, observability, security review, and deployment readiness.

## Phase 6 — Paper trading and evaluation
Simulated execution only, risk limits, and performance reporting. Live trading requires a separate explicit design and safety review.

Each phase is gated by tests and acceptance review. No profit guarantee.
