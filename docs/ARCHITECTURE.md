# Architecture — Phase 1

## Principles
Research and decision support first; no exchange order execution. Keep provider integrations behind future service adapters. Separate API, services, persistence, and configuration. Fail safely: generic client errors, detailed server logs, no secrets in source.

## Components
- Flutter client: presentation and future API consumption.
- FastAPI: versioned HTTP API and health probes.
- SQLAlchemy: persistence abstraction; SQLite locally, PostgreSQL intended.
- GitHub Actions: repeatable backend lint and test checks.

## Flow
Flutter → FastAPI router → service layer → SQLAlchemy session → database. Market-data providers will be added behind adapters in a later phase.

## Security baseline
Environment configuration, restrictive CORS defaults, no embedded credentials, and no trading endpoints in Phase 1.
