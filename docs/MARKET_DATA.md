# Phase 2 — Market data

## Current provider
- Binance public Spot REST klines via the /api/v3/klines endpoint for historical OHLCV candles.
- Binance public WebSocket kline consumer normalizes stream messages into the same UTC candle structure; it reconnects with bounded exponential backoff and is not started automatically by the API.

## Normalization and quality
All exchange timestamps are converted from Unix milliseconds to timezone-aware UTC datetimes. OHLCV and trade-count fields are normalized into a provider-neutral candle structure. Validation rejects malformed rows, negative values, inconsistent OHLC ranges, invalid time ordering, and duplicate timestamps.

## Persistence and API
GET /api/v1/market/candles?symbol=BTCUSDT&interval=1h&limit=200 fetches public candles and stores/upserts them in the candles table. The response includes provider, symbol, timeframe, count, inserted count, and normalized candles.

The API creates tables on startup. SQLite is the zero-setup local default; PostgreSQL can be configured with DATABASE_URL. No exchange API key is required for these public endpoints.

## Operational notes
- Public exchange availability, regional access, rate limits, and symbol support can change.
- The endpoint is network-dependent and returns HTTP 502 when the provider cannot be reached or returns invalid data.
- WebSocket streaming is a reusable service, not yet connected to persistent background workers or Flutter.
- No trading, account access, or order placement is implemented.
