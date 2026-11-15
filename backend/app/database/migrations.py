from sqlalchemy import Engine, inspect, text


def migrate_schema(engine: Engine) -> None:
    """Apply safe, additive compatibility migrations for existing databases.

    SQLAlchemy create_all() does not add columns to existing tables. This migration
    only adds the nullable taker_buy_volume column and never drops or rewrites data.
    """
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("candles"):
            return
        columns = {column["name"] for column in inspector.get_columns("candles")}
        if "taker_buy_volume" not in columns:
            connection.execute(
                text("ALTER TABLE candles ADD COLUMN taker_buy_volume FLOAT")
            )
