from sqlalchemy import Engine, inspect, text


def migrate_schema(engine: Engine) -> None:
    """Apply idempotent additive migrations required by serverless deployments.

    PostgreSQL advisory locking serializes concurrent Vercel cold starts.
    Vercel does not call SQLAlchemy metadata.create_all(), so every table used
    by request handlers must be created explicitly here.
    """
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text(
                "SELECT pg_advisory_xact_lock(hashtext('crypto-ai-schema-migrations'))"
            ))

            # Market data tables. Existing installations are left untouched;
            # the additive taker_buy_volume column supports older candle schemas.
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS candles (
                    id SERIAL PRIMARY KEY,
                    provider VARCHAR(30) NOT NULL DEFAULT 'binance',
                    symbol VARCHAR(30) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL,
                    open_time TIMESTAMPTZ NOT NULL,
                    close_time TIMESTAMPTZ NOT NULL,
                    open FLOAT NOT NULL,
                    high FLOAT NOT NULL,
                    low FLOAT NOT NULL,
                    close FLOAT NOT NULL,
                    volume FLOAT NOT NULL,
                    quote_volume FLOAT NOT NULL,
                    trades INTEGER NOT NULL,
                    taker_buy_volume FLOAT,
                    fetched_at TIMESTAMPTZ NOT NULL,
                    CONSTRAINT uq_candle_identity
                        UNIQUE (provider, symbol, timeframe, open_time)
                )
            """))
            connection.execute(text(
                "ALTER TABLE candles ADD COLUMN IF NOT EXISTS taker_buy_volume FLOAT"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_candles_symbol ON candles (symbol)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_candles_symbol_timeframe_open "
                "ON candles (symbol, timeframe, open_time)"
            ))

            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(30) NOT NULL,
                    timeframe VARCHAR(10) NOT NULL DEFAULT '1h',
                    price FLOAT NOT NULL,
                    source VARCHAR(40) NOT NULL DEFAULT 'manual',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_market_snapshots_id ON market_snapshots (id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_market_snapshots_symbol ON market_snapshots (symbol)"
            ))

            # Persisted order-flow and liquidation observations.
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS cvd_buckets (
                    id SERIAL PRIMARY KEY,
                    symbol VARCHAR(30) NOT NULL,
                    source_market VARCHAR(40) NOT NULL,
                    bucket_start_time TIMESTAMPTZ NOT NULL,
                    buy_volume FLOAT NOT NULL,
                    sell_volume FLOAT NOT NULL,
                    delta FLOAT NOT NULL,
                    trade_count INTEGER NOT NULL,
                    CONSTRAINT uq_cvd_bucket
                        UNIQUE (symbol, source_market, bucket_start_time)
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_cvd_symbol_bucket "
                "ON cvd_buckets (symbol, bucket_start_time)"
            ))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS cvd_collector_states (
                    symbol VARCHAR(30) PRIMARY KEY,
                    last_trade_id BIGINT NOT NULL DEFAULT -1,
                    updated_at TIMESTAMPTZ NOT NULL
                )
            """))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS liquidation_records (
                    id SERIAL PRIMARY KEY,
                    event_key VARCHAR(100) NOT NULL,
                    symbol VARCHAR(30) NOT NULL,
                    side VARCHAR(4) NOT NULL,
                    price FLOAT NOT NULL,
                    quantity FLOAT NOT NULL,
                    notional FLOAT NOT NULL,
                    timestamp TIMESTAMPTZ NOT NULL,
                    CONSTRAINT uq_liquidation_event_key UNIQUE (event_key)
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_liquidation_symbol_time "
                "ON liquidation_records (symbol, timestamp)"
            ))

            # Signal history and in-app notification inbox.
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS signal_events (
                    id SERIAL PRIMARY KEY,
                    dedupe_key VARCHAR(160) NOT NULL,
                    symbol VARCHAR(30) NOT NULL,
                    side VARCHAR(12) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                    timeframe_set VARCHAR(80) NOT NULL,
                    reasons_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_signal_event_dedupe UNIQUE (dedupe_key)
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_signal_event_symbol_created "
                "ON signal_events (symbol, created_at)"
            ))
            # Normalize any legacy duplicates before enforcing the active lock.
            connection.execute(text("""
                UPDATE signal_events
                SET status = 'INVALIDATED', updated_at = NOW()
                WHERE status = 'ACTIVE'
                  AND id NOT IN (
                    SELECT MAX(id) FROM signal_events
                    WHERE status = 'ACTIVE' GROUP BY symbol
                  )
            """))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_signal_event_one_active_per_symbol "
                "ON signal_events (symbol) WHERE status = 'ACTIVE'"
            ))
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS signal_notifications (
                    id SERIAL PRIMARY KEY,
                    signal_id INTEGER NOT NULL,
                    title VARCHAR(160) NOT NULL,
                    message TEXT NOT NULL,
                    read_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_signal_notifications_signal_id "
                "ON signal_notifications (signal_id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_signal_notification_created "
                "ON signal_notifications (created_at)"
            ))

            # Device registrations used by Firebase Cloud Messaging.
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS device_tokens (
                    id SERIAL PRIMARY KEY,
                    token VARCHAR(4096) NOT NULL UNIQUE,
                    platform VARCHAR(20) NOT NULL DEFAULT 'android',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_device_tokens_active "
                "ON device_tokens (is_active)"
            ))
            return

        # Local SQLite development uses Base.metadata.create_all() before this
        # migration. Keep this additive path for older local databases.
        inspector = inspect(connection)
        if inspector.has_table("candles"):
            columns = {column["name"] for column in inspector.get_columns("candles")}
            if "taker_buy_volume" not in columns:
                connection.execute(
                    text("ALTER TABLE candles ADD COLUMN taker_buy_volume FLOAT")
                )
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS device_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token VARCHAR(4096) NOT NULL UNIQUE,
                platform VARCHAR(20) NOT NULL DEFAULT 'android',
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_device_tokens_active ON device_tokens (is_active)"
        ))
        if inspect(connection).has_table("signal_events"):
            connection.execute(text("""
                UPDATE signal_events
                SET status = 'INVALIDATED'
                WHERE status = 'ACTIVE'
                  AND id NOT IN (
                    SELECT MAX(id) FROM signal_events
                    WHERE status = 'ACTIVE' GROUP BY symbol
                  )
            """))
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_signal_event_one_active_per_symbol "
                "ON signal_events (symbol) WHERE status = 'ACTIVE'"
            ))
