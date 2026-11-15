# Crypto AI Intelligence

Foundation scaffold for an AI-assisted crypto market analysis platform. This project is **analysis-only**: it does not place, modify, or cancel exchange orders.

## Current status
Phase 1 foundation scaffold:
- FastAPI backend with versioned health endpoint
- Environment-based configuration
- Structured application logging
- Consistent API error responses
- SQLAlchemy database foundation (SQLite by default)
- Basic backend tests
- Flutter Material 3 dark starter screen
- GitHub Actions backend test workflow
- Architecture, API, database, security, and roadmap documentation

Not implemented yet: live market scanning, technical-analysis signals, order-flow/liquidation data, push notifications, chart feeds, or performance analytics. The starter UI deliberately labels these as planned.

## Requirements
- Python 3.11+
- Flutter SDK (for the Android app)
- Git

## Run backend locally
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/api/v1/health`.

## Run backend tests
```bash
cd backend
pip install -r requirements.txt
pytest
```

## Run Flutter starter
```bash
cd frontend
flutter pub get
flutter run
```

## Configuration
Copy `.env.example` to `.env`. Never commit `.env`, API keys, passwords, tokens, or private credentials.

## Safety
This software is informational only. Any future signal must include source data, timestamp, timeframe, invalidation, and risk levels. No signal should be presented as guaranteed or as personalized financial advice.
