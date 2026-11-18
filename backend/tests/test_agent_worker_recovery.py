from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.agent_analysis_job import AgentAnalysisJob
from agent_worker import recover_stale_agent_jobs


def test_recover_stale_agent_jobs_requeues_only_expired_running_jobs():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False)
    now = datetime.now(timezone.utc)

    with session_factory() as db:
        stale = AgentAnalysisJob(
            symbol="BTCUSDT",
            ticker="BTC-USD",
            status="RUNNING",
            started_at=now - timedelta(hours=3),
        )
        fresh = AgentAnalysisJob(
            symbol="ETHUSDT",
            ticker="ETH-USD",
            status="RUNNING",
            started_at=now - timedelta(minutes=20),
        )
        pending = AgentAnalysisJob(
            symbol="SOLUSDT",
            ticker="SOL-USD",
            status="PENDING",
        )
        db.add_all([stale, fresh, pending])
        db.commit()
        stale_id, fresh_id, pending_id = stale.id, fresh.id, pending.id

        recovered = recover_stale_agent_jobs(db, stale_after_minutes=120)
        db.commit()

        assert recovered == 1
        stale_after = db.get(AgentAnalysisJob, stale_id)
        fresh_after = db.get(AgentAnalysisJob, fresh_id)
        pending_after = db.get(AgentAnalysisJob, pending_id)

        assert stale_after.status == "PENDING"
        assert stale_after.started_at is None
        assert "requeued" in stale_after.error_message.lower()
        assert fresh_after.status == "RUNNING"
        assert pending_after.status == "PENDING"

    engine.dispose()
