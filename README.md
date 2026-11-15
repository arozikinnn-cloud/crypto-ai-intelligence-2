# Crypto AI Intelligence
Research-first crypto market analysis platform. Phase 1 is the foundation only: it does not place trades or execute exchange orders.

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

Run tests: `cd backend && pytest -q`.

Never commit real credentials. Live trading and order execution are explicitly out of scope for Phase 1. See docs/ROADMAP.md.