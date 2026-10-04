from app.services.page_split import present_full, present_summary, present_ticket
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import NowDep
from app.database import get_db
from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize
from app.services.time_window import OUTSIDE_REASON, location_open
router = APIRouter(prefix="/refills", tags=["refills"])


def _latest_order(db: Session, location_id: int) -> RefillOrder | None:
    return db.scalars(select(RefillOrder).where(RefillOrder.location_id == location_id)
                      .order_by(RefillOrder.id.desc())).first()


def _serialize(order: RefillOrder, location_id: int, loc: Location, now: datetime) -> dict:
    data = json.loads(order.lines_json)
    return {
        "id": order.id,
        "location_id": location_id,
        "fill_start_minute": loc.fill_start_minute,
        "fill_end_minute": loc.fill_end_minute,
        "fill_open": location_open(loc, now=now),
        **data,
    }


def generate_refill(db: Session, loc: Location, now: datetime) -> dict:
    """落新单的唯一入口：窗外直接失败，绝不写单；窗内按现网规则生成。

    点位页窗配置、本生成接口、补货单列表（latest/full/summary 的首单路径）
    共用此口径。
    """
    if not location_open(loc, now=now):
        raise HTTPException(status_code=403, detail=OUTSIDE_REASON)
    lanes = db.scalars(select(Lane).where(Lane.location_id == loc.id).order_by(Lane.slot_no)).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    summary = summarize(build_fill_lines(payload))
    order = RefillOrder(location_id=loc.id, created_at=datetime.utcnow(),
                        lines_json=json.dumps(summary, ensure_ascii=False))
    db.add(order); db.commit(); db.refresh(order)
    return _serialize(order, loc.id, loc, now)


@router.post("/run")
def run_refill(location_id: int = 1, db: Session = Depends(get_db), now: datetime = NowDep):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "点位不存在")
    # 以数据库中刚保存的窗界当场判定：窗外不新增任何补货单。
    return generate_refill(db, loc, now)


@router.get("/latest")
def latest(location_id: int = 1, db: Session = Depends(get_db), now: datetime = NowDep):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(404, "点位不存在")
    order = _latest_order(db, location_id)
    if order is None:
        # 尚无成功单：窗内才允许首单；窗外同样失败且不写单。
        return generate_refill(db, loc, now)
    return _serialize(order, location_id, loc, now)


@router.get("/full")
def full_lanes(location_id: int = 1, db: Session = Depends(get_db), now: datetime = NowDep):
    data = latest(location_id=location_id, db=db, now=now)
    return present_full(location_id, data)

@router.get("/summary")
def refill_summary(location_id: int = 1, db: Session = Depends(get_db), now: datetime = NowDep):
    data = latest(location_id=location_id, db=db, now=now)
    return present_summary(location_id, data)

