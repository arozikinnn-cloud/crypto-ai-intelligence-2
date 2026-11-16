import json
import logging
import os
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _firebase_app():
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        logger.info("FCM disabled: FIREBASE_SERVICE_ACCOUNT_JSON is not configured")
        return None
    try:
        info = json.loads(raw)
        if info.get("project_id") != "crypto-ai-intelligence-v7":
            raise ValueError("Firebase service account project_id does not match the app")
        try:
            return firebase_admin.get_app()
        except ValueError:
            return firebase_admin.initialize_app(credentials.Certificate(info))
    except Exception:
        logger.exception("Unable to initialize Firebase Admin SDK")
        return None


def send_push_to_registered_devices(
    db: Session, *, title: str, body: str, data: dict[str, str] | None = None
) -> dict[str, int]:
    app = _firebase_app()
    if app is None:
        return {"sent": 0, "failed": 0, "configured": 0}
    rows = list(db.scalars(select(DeviceToken).where(DeviceToken.is_active.is_(True))))
    if not rows:
        return {"sent": 0, "failed": 0, "configured": 1}
    sent = failed = 0
    for start in range(0, len(rows), 500):
        batch = rows[start:start + 500]
        message = messaging.MulticastMessage(
            tokens=[row.token for row in batch],
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(priority="high"),
        )
        try:
            response = messaging.send_each_for_multicast(message, app=app)
            sent += response.success_count
            failed += response.failure_count
            for row, result in zip(batch, response.responses):
                if not result.success:
                    code = getattr(getattr(result.exception, "code", None), "value", "")
                    if code in {"registration-token-not-registered", "invalid-argument"}:
                        row.is_active = False
            db.commit()
        except Exception:
            logger.exception("FCM multicast send failed")
            failed += len(batch)
    return {"sent": sent, "failed": failed, "configured": 1}
