import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.analysis.tradingagents_result import normalize_tradingagents_result


@pytest.mark.parametrize(
    ("rating", "expected"),
    [
        ("Buy", "BUY"),
        ("Overweight", "BUY"),
        ("Hold", "NO TRADE"),
        ("Underweight", "SELL"),
        ("Sell", "SELL"),
        ("REVIEW", "NO TRADE"),
        ("unrecognized", "NO TRADE"),
    ],
)
def test_tradingagents_rating_mapping_is_conservative(rating, expected):
    result = normalize_tradingagents_result(rating, "Example decision")
    assert result["side"] == expected
    assert result["execution_ready"] is False
    assert result["engine"] == "TradingAgents"


def test_tradingagents_result_never_invents_order_levels():
    result = normalize_tradingagents_result("Buy", "Rating: Buy")
    assert result["side"] == "BUY"
    assert "entry" not in result
    assert "stop_loss" not in result
    assert "take_profit" not in result


def test_agent_job_endpoint_is_disabled_until_worker_and_provider_are_configured(monkeypatch):
    from app.api import agent_analysis

    monkeypatch.setattr(
        agent_analysis,
        "get_settings",
        lambda: type("Settings", (), {"tradingagents_enabled": False})(),
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/agent-analysis/jobs?symbol=BTCUSDT")
    assert response.status_code == 503
    assert "worker and model provider" in response.json()["detail"]



def test_agent_job_enqueue_requires_server_only_token(monkeypatch):
    from app.api import agent_analysis

    monkeypatch.setattr(
        agent_analysis,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"tradingagents_enabled": True, "tradingagents_enqueue_token": "private-token"},
        )(),
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/agent-analysis/jobs?symbol=BTCUSDT")
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]


def test_agent_job_enqueue_stays_locked_when_server_token_is_not_configured(monkeypatch):
    from app.api import agent_analysis

    monkeypatch.setattr(
        agent_analysis,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"tradingagents_enabled": True, "tradingagents_enqueue_token": ""},
        )(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent-analysis/jobs?symbol=BTCUSDT",
            headers={"X-TradingAgents-Enqueue-Token": "anything"},
        )
    assert response.status_code == 503
    assert "server-only" in response.json()["detail"]


def test_agent_job_enqueue_accepts_matching_server_token(monkeypatch):
    from app.api import agent_analysis

    monkeypatch.setattr(
        agent_analysis,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"tradingagents_enabled": True, "tradingagents_enqueue_token": "private-token"},
        )(),
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/agent-analysis/jobs?symbol=BTCUSDT",
            headers={"X-TradingAgents-Enqueue-Token": "private-token"},
        )
    assert response.status_code == 202
    assert response.json()["symbol"] == "BTCUSDT"
    assert response.json()["status"] == "PENDING"
