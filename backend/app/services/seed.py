import json
from datetime import datetime, timedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Lane, Location, RefillOrder, Sale
from app.services.fill_engine import build_fill_lines, summarize
from app.services.time_window import current_minute

# 极窄补货窗宽度（分钟）。种子取一个保证落在当前时刻之外的 1 分钟窗。
NARROW_WINDOW_MINUTES = 1


def narrow_window_away_from_now(now: datetime | None = None) -> tuple[int, int]:
    """返回一个极窄、且当前时刻必然在窗外的半开区间 [start, start+1)。

    取"当前分钟 + 60 分钟（模 1440）"作为窗起点，离当前时刻至少约一小时。
    """
    minute = current_minute(now)
    start = (minute + 60) % (24 * 60)
    if start + NARROW_WINDOW_MINUTES > 24 * 60 - 1:
        start = 0
    return start, start + NARROW_WINDOW_MINUTES


def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Location)) or 0) > 0:
        return
    start, end = narrow_window_away_from_now()
    loc = Location(code="VM-01", name="地铁口 A 点位", address="城东地铁 1 号口",
                   fill_start_minute=start, fill_end_minute=end)
    db.add(loc); db.flush()
    lanes = [
        ("A1", "矿泉水", 20, 5, 0),
        ("A2", "可乐", 18, 18, 0),
        ("B1", "薯片", 12, 3, 2),
        ("B2", "巧克力", 15, 10, 5),
        ("C1", "能量棒", 10, 0, 0),
        ("C2", "口香糖", 24, 24, 2),
    ]
    lane_ids = []
    payload = []
    for slot, sku, cap, stock, transit in lanes:
        lane = Lane(location_id=loc.id, slot_no=slot, sku_name=sku, capacity=cap, stock=stock, in_transit=transit)
        db.add(lane); db.flush()
        lane_ids.append(lane.id)
        payload.append({"id": lane.id, "slot_no": slot, "sku_name": sku,
                        "capacity": cap, "stock": stock, "in_transit": transit})
    now = datetime(2026, 9, 16, 12, 0, 0)
    for i, lid in enumerate(lane_ids):
        db.add(Sale(lane_id=lid, qty=2 + i, sold_at=now - timedelta(hours=i)))
    # 预置最近一次成功补货单：窗外点生成失败、条数不增加时，页面仍展示本单。
    summary = summarize(build_fill_lines(payload))
    db.add(RefillOrder(location_id=loc.id, created_at=now - timedelta(minutes=30),
                       lines_json=json.dumps(summary, ensure_ascii=False)))
    db.commit()
