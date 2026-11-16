# Persistent background worker

## Purpose

Vercel Functions are short-lived serverless invocations and must not host
permanent WebSocket connections. The standalone worker in `worker.py` is the
persistent-process entry point for Binance public market streams:

- Spot `<symbol>@aggTrade` for trade-side volume/CVD collection.
- USD-M Futures `<symbol>@forceOrder` for liquidation-event collection.
- Both existing collectors batch writes to the configured SQL database and
  reconnect with exponential backoff after disconnects.

This worker is separate from the FastAPI API process. It does not submit,
modify, or cancel exchange orders.

## Container build

Build from the `backend/` directory:

```sh
docker build -f Dockerfile.worker -t crypto-ai-worker .
docker run --env-file .env crypto-ai-worker
```

Required environment:

- `DATABASE_URL`: shared PostgreSQL database URL. Production worker startup
  now rejects SQLite so it cannot silently write to an isolated container disk.
  The URL must point to the same durable database used by the API.
- `CVD_COLLECTOR_ENABLED=true`
- `CVD_COLLECTOR_SYMBOLS=BTCUSDT,ETHUSDT` (adjust to available DB capacity)
- `LIQUIDATION_COLLECTOR_ENABLED=true`
- `LIQUIDATION_COLLECTOR_SYMBOLS=BTCUSDT,ETHUSDT`

The current defaults are conservative and collect BTCUSDT only. Never commit
`.env`, database credentials, Firebase service-account JSON, or API secrets.

## Important operational limits

- Deploy this container only to a host that supports an always-running worker
  process. Do not deploy it as a Vercel Function.
- This repository change prepares the worker; it does not provision a host,
  create a paid resource, or start a production process.
- A free host may sleep, restart, or impose CPU/network limits. Confirm its
  current free-tier policy before selecting it. No paid plan is authorized.
- Configure restart-on-failure and inspect worker logs. The worker exits with
  an error if a collector task unexpectedly stops, allowing the host supervisor
  to restart it. The collectors reconnect after network interruptions, but
  database outages can still delay persistence.
- The container runs as a non-root user.
- A WebSocket collector is not itself an AI signal generator. The existing
  scheduled intelligence endpoint remains a separate periodic scan. To claim
  end-to-end 24/7 automated signals, both processes must be deployed, share a
  durable database, and pass live tests for stored events, signal creation,
  and FCM delivery.

## Local verification

From `backend/` run:

```sh
pytest -q
ruff check .
```
