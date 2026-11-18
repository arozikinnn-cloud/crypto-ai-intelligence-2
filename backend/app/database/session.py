import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()
database_url = settings.database_url.strip()
# Vercel Preview may have no shared PostgreSQL credential. Use writable
# ephemeral storage rather than the repository-relative, read-only SQLite path.
# This fallback is for preview smoke tests only; it is not durable storage.
if os.getenv("VERCEL") == "1" and not os.getenv("DATABASE_URL"):
    database_url = "sqlite:////tmp/crypto_ai_preview.db"
# Supabase commonly provides postgresql:// URLs; this project installs psycopg 3.
if database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )
connect_args = (
    {"check_same_thread": False} if database_url.startswith("sqlite") else {}
)
engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
