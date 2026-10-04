from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import NowDep
from app.database import get_db
from app.models.models import Location
from app.services.time_window import location_open, validate_window
router = APIRouter(prefix="/locations", tags=["locations"])

class LocationWindowIn(BaseModel):
    fill_start_minute: int | None = None
    fill_end_minute: int | None = None


def serialize(loc: Location, now: datetime) -> dict:
    return {
        "id": loc.id,
        "code": loc.code,
        "name": loc.name,
        "address": loc.address,
        "fill_start_minute": loc.fill_start_minute,
        "fill_end_minute": loc.fill_end_minute,
        "fill_open": location_open(loc, now=now),
    }

@router.get("")
def list_locations(db: Session = Depends(get_db), now: datetime = NowDep):
    return [serialize(r, now) for r in db.scalars(select(Location).order_by(Location.id)).all()]

@router.put("/{location_id}")
def update_location(location_id: int, body: LocationWindowIn, db: Session = Depends(get_db),
                    now: datetime = NowDep):
    """保存点位补货时段窗。非法窗（结束不大于开始、越界、只填一端）一律拒绝，
    点位与单据保持改前。"""
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "点位不存在")
    reason = validate_window(body.fill_start_minute, body.fill_end_minute)
    if reason is not None:
        db.rollback()
        raise HTTPException(400, reason)
    loc.fill_start_minute = body.fill_start_minute
    loc.fill_end_minute = body.fill_end_minute
    db.commit()
    db.refresh(loc)
    return serialize(loc, now)
