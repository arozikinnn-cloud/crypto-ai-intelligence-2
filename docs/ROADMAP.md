# Project roadmap

## Phase 1 — Foundation
Repository structure, FastAPI app, versioned API, configuration, logging, error handling, CORS baseline, SQLAlchemy session/model, health probes, tests, CI, architecture/API/database docs, and Flutter shell.

## Phase 2 — Market data
Public Binance Spot REST candle ingestion, normalized UTC OHLCV schema, candle quality validation, historical candle persistence/upsert, market-data API, and an opt-in reconnecting Binance WebSocket consumer. Provider credentials are not required for public market data.

## Phase 3 — Analysis engine — implemented baseline; validation still required
Explainable technical analysis, closed-candle multi-timeframe confluence, SMC heuristics, kline and aggTrades order flow, persistent observed-history CVD collector/API, separate Futures OI/funding context, force-order liquidation collector/history API, live order-book imbalance snapshot (not absorption), persistent CVD and observed liquidation context in combined intelligence, evidence-gated confluence, EMA baseline backtest, single-position combined historical backtest with candle-gap validation, out-of-sample metrics/quality gates, timeframe comparison endpoint, and bounded REST retry handling are present in the backend. This is a deterministic rule-based research engine, not a calibrated AI probability model. Remaining gaps: reliable historical backfill and completeness during outages, historical order-book/footprint series, validated absorption, historical replay of aggTrades/liquidations/OI/funding/news, broad multi-symbol validation, and independent walk-forward evaluation, statistically meaningful out-of-sample trade sample, and broader symbol/regime coverage.

## Phase 4 — Signals and notifications — partial
Persistent signal events, active-signal deduplication, opposite-signal/NO TRADE invalidation, manual close, notification inbox polling, and read/unread state are implemented. Remaining: Android push delivery (FCM), device-token registration, per-user preferences, notification delivery retries, authentication/ownership isolation, and alert audit/analytics. Current notification inbox requires the app to poll the API; it does not send a push while the app is closed.

## Phase 5 — App integration and hardening
Flutter dashboards, watchlists, signal details, authenticated user accounts, rate limits, observability, security review, notification UI/push integration, and deployment readiness.

## Phase 6 — Paper trading and evaluation
Simulated execution only, risk limits, walk-forward testing, and performance reporting. Live trading is out of scope and would require a separate explicit design and safety review.

Each phase is gated by tests and acceptance review. No profit guarantee.
