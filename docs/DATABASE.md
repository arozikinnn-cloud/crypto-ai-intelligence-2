# Database foundation

Phase 1 defines SQLAlchemy 2 metadata and a starter `market_snapshots` table.

| Field | Type | Purpose |
|---|---|---|
| id | integer | Primary key |
| symbol | varchar(30) | Market symbol |
| timeframe | varchar(10) | Candle timeframe |
| price | float | Observed price |
| source | varchar(40) | Data source |
| created_at | timestamp | Snapshot creation time |

Local default: SQLite. Intended deployment: PostgreSQL via `DATABASE_URL`. Alembic migrations, retention policy, analytics indexes, and production backups are deferred.
