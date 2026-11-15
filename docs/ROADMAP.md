# Project roadmap

## Phase 1 — Foundation
Repository structure, FastAPI app, versioned API, configuration, logging, error handling, CORS baseline, SQLAlchemy session/model, health probes, tests, CI, architecture/API/database docs, and Flutter shell.

## Phase 2 — Market data
Public Binance Spot REST candle ingestion, normalized UTC OHLCV schema, candle quality validation, historical candle persistence/upsert, market-data API, and an opt-in reconnecting Binance WebSocket consumer. Provider credentials are not required for public market data.

## Phase 3 — Analysis engine
Explainable technical analysis, closed-candle multi-timeframe confluence, SMC heuristics (confirmed pivots/BOS/CHOCH, liquidity sweeps, last-opposing-candle order-block zones, FVG mitigation flags), Binance Spot kline-derived order-flow delta/CVD-window proxy, separate trade-level Binance Spot aggTrades aggressor-delta endpoint, persisted taker-buy candle volume with additive schema migration, separate Binance USD-M Futures OI/funding context, combined evidence-gated NO TRADE/BUY/SELL endpoint, live Futures force-order liquidation WebSocket pass-through, and EMA crossover backtesting with estimated costs and out-of-sample evaluation. This remains a deterministic rule-based research engine, not a calibrated AI probability model. Full order-book/footprint, persistent session CVD, liquidation heatmap/aggregation, validated absorption, news/fundamental/sentiment, durable signal lifecycle, and model calibration remain future extensions.

## Phase 4 — Signals and notifications
Signal lifecycle, deduplication, push notifications, user preferences, and alert audit trail.

## Phase 5 — App integration and hardening
Flutter dashboards, watchlists, signal details, authentication, rate limits, observability, security review, and deployment readiness.

## Phase 6 — Paper trading and evaluation
Simulated execution only, risk limits, and performance reporting. Live trading requires a separate explicit design and safety review.

Each phase is gated by tests and acceptance review. No profit guarantee.
