# Crypto AI Intelligence
Research-first crypto market analysis platform. It analyzes public market data and does not place trades or execute exchange orders.

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

Run tests: `cd backend && pytest -q`.

Never commit real credentials. Live trading and order execution are explicitly out of scope for Phase 1. See docs/ROADMAP.md.