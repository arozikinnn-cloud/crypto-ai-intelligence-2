from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.device_token import DeviceToken

router = APIRouter(prefix="/devices", tags=["push notification devices"])


class DeviceRegistration(BaseModel):
    token: str = Field(min_length=40, max_length=4096)
    platform: str = Field(default="android", pattern="^android$")


@router.post("/fcm-token")
def register_fcm_token(payload: DeviceRegistration, db: Session = Depends(get_db)):
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=422, detail="FCM token is empty")
    row = db.scalar(select(DeviceToken).where(DeviceToken.token == token))
    now = datetime.now(timezone.utc)
    if row is None:
        row = DeviceToken(token=token, platform=payload.platform, is_active=True,
                          created_at=now, updated_at=now)
        db.add(row)
    else:
        row.platform = payload.platform
        row.is_active = True
        row.updated_at = now
    db.commit()
    return {"registered": True, "platform": row.platform}


@router.delete("/fcm-token")
def unregister_fcm_token(payload: DeviceRegistration, db: Session = Depends(get_db)):
    row = db.scalar(select(DeviceToken).where(DeviceToken.token == payload.token.strip()))
    if row is not None:
        row.is_active = False
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
    return {"registered": False, "unregistered": True}
