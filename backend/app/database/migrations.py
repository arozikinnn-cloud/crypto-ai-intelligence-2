from sqlalchemy import Engine, inspect, text


def migrate_schema(engine: Engine) -> None:
    """Apply idempotent additive migrations.

    PostgreSQL advisory locking serializes concurrent Vercel cold starts.
    Only explicit CREATE TABLE/INDEX statements are used here; no metadata
    create_all() or implicit PostgreSQL type creation is performed.
    """
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text(
                "SELECT pg_advisory_xact_lock(hashtext('crypto-ai-schema-migrations'))"
            ))
            connection.execute(text(
                "ALTER TABLE candles ADD COLUMN IF NOT EXISTS taker_buy_volume FLOAT"
            ))
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
                "CREATE INDEX IF NOT EXISTS ix_device_tokens_active ON device_tokens (is_active)"
            ))
            return

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
