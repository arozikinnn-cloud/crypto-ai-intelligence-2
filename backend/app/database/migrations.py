from sqlalchemy import Engine, inspect, text


def migrate_schema(engine: Engine) -> None:
    """Apply safe, additive compatibility migrations without recreating tables.

    PostgreSQL's IF NOT EXISTS makes this single-column migration safe when
    several Vercel serverless instances start at the same time.
    """
    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text(
                "ALTER TABLE candles ADD COLUMN IF NOT EXISTS taker_buy_volume FLOAT"
            ))
            return

        inspector = inspect(connection)
        if not inspector.has_table("candles"):
            return
        columns = {column["name"] for column in inspector.get_columns("candles")}
        if "taker_buy_volume" not in columns:
            connection.execute(
                text("ALTER TABLE candles ADD COLUMN taker_buy_volume FLOAT")
            )
