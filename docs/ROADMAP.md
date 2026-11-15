# Project roadmap

## Phase 1 — Foundation
Repository structure, FastAPI app, versioned API, configuration, logging, error handling, CORS baseline, SQLAlchemy session/model, health probes, tests, CI, architecture/API/database docs, and Flutter shell.

## Phase 2 — Market data
Public Binance Spot REST candle ingestion, normalized UTC OHLCV schema, candle quality validation, historical candle persistence/upsert, market-data API, and an opt-in reconnecting Binance WebSocket consumer. Provider credentials are not required for public market data.

## Phase 3 — Analysis engine — implemented baseline; validation still required
Explainable technical analysis, closed-candle multi-timeframe confluence, SMC heuristics, kline and aggTrades order flow, persistent observed-history CVD collector/API, separate Futures OI/funding context, force-order liquidation collector/history API, live order-book imbalance snapshot (not absorption), persistent CVD and observed liquidation context in combined intelligence, evidence-gated confluence, EMA baseline backtest, single-position combined historical backtest with candle-gap validation, out-of-sample metrics/quality gates, timeframe comparison endpoint, and bounded REST retry handling are present in the backend. This is a deterministic rule-based research engine, not a calibrated AI probability model. Remaining gaps: reliable historical backfill and completeness during outages, historical order-book/footprint series, validated absorption, historical replay of aggTrades/liquidations/OI/funding/news, broad multi-symbol validation, and independent walk-forward evaluation, statistically meaningful out-of-sample trade sample, and broader symbol/regime coverage.

## Phase 4 — Signals and notifications — partial
Persistent signal events, active-signal deduplication, opposite-signal/NO TRADE invalidation, manual close, notification inbox polling, and read/unread state are implemented. The Flutter dashboard now refreshes the inbox every 30 seconds while foregrounded and refreshes immediately when the app resumes. Remaining: Android push delivery (FCM), device-token registration, per-user preferences, notification delivery retries, authentication/ownership isolation, and alert audit/analytics. Polling is foreground-only and does not deliver alerts while the app is closed.

## Phase 5 — App integration and hardening
Flutter dashboards, watchlists, signal details, authenticated user accounts, rate limits, observability, security review, notification UI/push integration, and deployment readiness.

## Phase 6 — Paper trading and evaluation
Not yet implemented as a user-facing simulated trade ledger. Required scope: simulated next-available fills, configurable maker/taker fees and slippage, stop-loss/take-profit execution rules, position sizing, max-risk and max-drawdown guards, immutable trade history, and performance reporting (expectancy, profit factor, win rate, drawdown). The existing historical backtests are research evaluation, not paper trading. Live trading is out of scope and would require a separate explicit design and safety review.

Each phase is gated by tests and acceptance review. No profit guarantee.


## Parallel delivery plan (Phase 3–6)

Workstreams can progress in parallel behind stable API contracts; integration is still gated by CI and end-to-end checks.

| Workstream | Scope | Exit criteria |
|---|---|---|
| A — Analysis quality | Phase 3: data continuity, collector gap visibility, multi-symbol/regime evaluation, walk-forward validation | Reproducible tests pass; no look-ahead; meaningful out-of-sample sample; limitations surfaced in API |
| B — Signal lifecycle | Phase 4: signal deduplication, invalidation, inbox, read state, delivery abstraction | Lifecycle tests cover BUY/SELL/NO TRADE; no duplicate alerts; delivery failures observable |
| C — Mobile integration | Phase 5: Flutter API client, dashboard, signal list/detail, notification inbox | Android build succeeds; configurable API base URL; loading/error/empty states; no secrets embedded |
| D — Paper evaluation | Phase 6: simulated fills, fees/slippage, risk limits, trade ledger, performance metrics | No exchange order endpoints; deterministic replay; fees included; drawdown and trade history verified |
| E — Integration and security | Cross-phase contracts, migrations, rate limits, authentication/ownership, dependency and API review | CI green; migration tested on fresh and existing DB; user data isolated before multi-user release |

### Delivery rules

- Parallel work must not bypass shared schemas, migrations, or API contracts.
- Every feature is marked implemented only after automated tests; mobile features also require an Android build.
- Market-data outages must be visible as unavailable/stale, never silently treated as valid confirmation.
- Push notifications are not considered complete until device registration, delivery, retry, and permission behavior are tested on Android.
- Paper trading is simulation only. No exchange order placement or live trading is part of this roadmap.
- Prefer free/public services. Any paid infrastructure requires explicit approval before adoption.


## Current integration notes (2026-11-15)

- Mobile CI builds a debug APK and uploads it as a 7-day workflow artifact; this is not a Play Store release.
- The APK artifact path was corrected to the Flutter workspace path.
- The mobile dashboard polls the in-app signal inbox every 30 seconds only while foregrounded, and refreshes on resume.
- A green build, device installation test, backend integration test, and Android push test are still required before calling the mobile release complete.
- No percentage-complete estimate is published until CI and end-to-end acceptance checks are observable.
