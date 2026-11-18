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

TradingAgents ratings map to BUY/SELL/NO TRADE conservatively. The research rating is not an executable order: this change does not invent entry/SL/TP, does not connect Hummingbot, and does not place live orders. A separate validated risk plan and Paper Trading adapter are required before execution is enabled.

Run tests: `cd backend && pytest -q`.

Never commit real credentials. See docs/ROADMAP.md.
