# Crypto AI Intelligence

Research-first crypto market analysis platform. V8 adds an isolated Tauric Research TradingAgents multi-agent research worker. No exchange orders are placed.

## Stack

Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy 2, SQLite locally / PostgreSQL intended, Flutter, pytest, Ruff, GitHub Actions.

## Backend

```bash
cd backend
python -m venv .venv
# activate the environment, then:
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```

Open `/docs`; liveness: `/api/v1/health`; readiness: `/api/v1/health/ready`.

By default, the backend starts public Binance Spot aggTrades and USD-M Futures force-order collectors for BTCUSDT. They reconnect automatically and persist observed CVD/liquidation events locally. Configure symbols and collector switches in `.env`. History endpoints:
- `GET /api/v1/analysis/order-flow/cvd-history?symbol=BTCUSDT&limit=500`
- `GET /api/v1/analysis/liquidations/history?symbol=BTCUSDT&hours=24`

Collectors only gather data while the backend process is running. Binance force-order data is partial and neither history is guaranteed gap-free. See docs/ANALYSIS_ENGINE.md and docs/ROADMAP.md.

## V8 TradingAgents

The former RSI/MA/Ichimoku decision engine is superseded by the upstream TradingAgents multi-agent research graph. The API only queues and serves analysis jobs; the heavy Python package runs in a separate persistent worker so Vercel's serverless API bundle stays lean.

- `POST /api/v1/agent-analysis/jobs?symbol=BTCUSDT`
- `GET /api/v1/agent-analysis/jobs/{id}`
- `GET /api/v1/agent-analysis/jobs?symbol=BTCUSDT&limit=20`

The feature is disabled by default. Set `TRADINGAGENTS_ENABLED=true` only after the agent worker, shared durable PostgreSQL database, persistent worker storage, and a model provider have been configured. Build the worker with `backend/Dockerfile.agent-worker`; see [docs/V8_TRADINGAGENTS_ROLLOUT.md](docs/V8_TRADINGAGENTS_ROLLOUT.md).

TradingAgents ratings are cross-checked against read-only Bitget USDT-M Futures data (5m/15m/30m/1h candles, order book, OI and funding). BUY/SELL requires agreement across the agent rating and 1h/30m/15m confirmation, with no opposing 5m direction. The candidate plan uses 15m ATR(14) x 1.5 for SL and 1:1.5 RR. Validated plans are stored in a V8-only forward signal journal and monitored against later closed Bitget 1m candles. This is not a historical TradingAgents backtest or a Hummingbot Paper Trade simulation. The V8 job API remains disabled until a shared durable database, persistent worker host/storage, and private model-provider credentials are configured. No live orders are placed.

Run tests: `cd backend && pytest -q`.

Never commit real credentials. See docs/ROADMAP.md.
