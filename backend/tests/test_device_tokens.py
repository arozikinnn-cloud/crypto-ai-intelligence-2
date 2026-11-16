from sqlalchemy import select

from app.database.session import SessionLocal
from app.main import app
from app.models.device_token import DeviceToken
from fastapi.testclient import TestClient


client = TestClient(app)


def test_fcm_device_token_registration_is_idempotent_and_revocable():
    token = "fcm-test-token-" + ("x" * 48)
    db = SessionLocal()
    try:
        db.query(DeviceToken).filter(DeviceToken.token == token).delete()
        db.commit()

        first = client.post(
            "/api/v1/devices/fcm-token",
            json={"token": token, "platform": "android"},
        )
        assert first.status_code == 200
        assert first.json() == {"registered": True, "platform": "android"}

        second = client.post(
            "/api/v1/devices/fcm-token",
            json={"token": token, "platform": "android"},
        )
        assert second.status_code == 200
        rows = list(db.scalars(select(DeviceToken).where(DeviceToken.token == token)))
        assert len(rows) == 1
        assert rows[0].is_active is True

        revoked = client.request(
            "DELETE",
            "/api/v1/devices/fcm-token",
            json={"token": token, "platform": "android"},
        )
        assert revoked.status_code == 200
        db.refresh(rows[0])
        assert rows[0].is_active is False
    finally:
        db.query(DeviceToken).filter(DeviceToken.token == token).delete()
        db.commit()
        db.close()


def test_fcm_device_token_rejects_invalid_payload():
    response = client.post(
        "/api/v1/devices/fcm-token",
        json={"token": "too-short", "platform": "android"},
    )
    assert response.status_code == 422
