# Architecture — Phase 2

## Principles
Research and decision support first; no exchange order execution. Provider integrations are isolated behind adapters. Separate API, services, persistence, and configuration. Fail safely and never store secrets in source.

## Components
- Flutter client: presentation shell; market-data screens are planned for Phase 5.
- FastAPI: versioned HTTP API and health probes.
- Binance adapter: public Spot REST klines and opt-in public WebSocket kline stream.
- Normalization and quality layer: provider-neutral OHLCV candles with UTC timestamps and validation.
- SQLAlchemy: candle persistence; SQLite locally, PostgreSQL supported through DATABASE_URL.
- GitHub Actions: backend lint and test checks.

## Data flow
REST request → Binance adapter → normalized candles → quality validation → SQLAlchemy upsert → API response.
The optional WebSocket consumer exposes parsed kline messages to a caller callback; persistent worker orchestration is not enabled yet.

## Security and scope
Public market data only. No exchange account credentials, private account endpoints, or order placement. Provider limits and availability apply.
