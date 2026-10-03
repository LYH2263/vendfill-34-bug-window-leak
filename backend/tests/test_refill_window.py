"""时段窗端到端口径：点位页窗配置、生成接口、补货单列表同一套放行规则。"""
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_now
from app.database import Base, get_db
from app.main import app
from app.models.models import Lane, Location, RefillOrder
from app.services.fill_engine import build_fill_lines, summarize


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)
    db = TestingSession()
    loc = Location(code="VM-01", name="测试点位", address="测试地址",
                   fill_start_minute=None, fill_end_minute=None)
    db.add(loc); db.flush()
    for slot, sku, cap, stock, transit in [
        ("A1", "矿泉水", 20, 5, 0),
        ("A2", "可乐", 18, 18, 0),
        ("C2", "口香糖", 24, 24, 2),
    ]:
        db.add(Lane(location_id=loc.id, slot_no=slot, sku_name=sku,
                    capacity=cap, stock=stock, in_transit=transit))
    db.commit()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    def _get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _get_db
    frozen = {"at": None}

    def _get_now():
        return frozen["at"]
    app.dependency_overrides[get_now] = _get_now
    c = TestClient(app)  # 不进入 with：跳过 lifespan（避免连真实 PG），表已在建库夹具中手动建好
    c.frozen = frozen  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def order_count(db) -> int:
    return db.scalar(select(func.count()).select_from(RefillOrder)) or 0


def seed_prior_order(db) -> None:
    """预置一张历史成功单（等价于种子数据里的最近一次成功单）。"""
    lanes = db.scalars(select(Lane).where(Lane.location_id == 1).order_by(Lane.slot_no)).all()
    payload = [{"id": l.id, "slot_no": l.slot_no, "sku_name": l.sku_name,
                "capacity": l.capacity, "stock": l.stock, "in_transit": l.in_transit} for l in lanes]
    db.add(RefillOrder(location_id=1, created_at=datetime.utcnow() - timedelta(minutes=30),
                       lines_json=json.dumps(summarize(build_fill_lines(payload)), ensure_ascii=False)))
    db.commit()


def test_unrestricted_window_generates_anytime(client, db_session):
    client.frozen["at"] = datetime(2026, 10, 3, 3, 33)
    r = client.post("/api/refills/run?location_id=1")
    assert r.status_code == 200
    assert order_count(db_session) == 1


def test_narrow_window_outside_fails_and_no_new_order(client, db_session):
    # 预置最近一次成功单（与种子口径一致）：窗外失败时页面仍展示它
    seed_prior_order(db_session)
    # 窗 [600, 601)：10:00 才放行，当前 03:33 必然在窗外
    assert client.put("/api/locations/1", json={"fill_start_minute": 600, "fill_end_minute": 601}).status_code == 200
    before = order_count(db_session)
    client.frozen["at"] = datetime(2026, 10, 3, 3, 33)

    r = client.post("/api/refills/run?location_id=1")
    assert r.status_code == 403
    assert r.json()["detail"] == "不在补货时段"
    assert order_count(db_session) == before  # 不得新增补货单

    # 列表与汇总仍只反映最近一次成功单，不偷写新单
    latest = client.get("/api/refills/latest?location_id=1")
    assert latest.status_code == 200
    assert latest.json()["fill_open"] is False
    assert order_count(db_session) == before
    full = client.get("/api/refills/full?location_id=1")
    assert full.status_code == 200
    summ = client.get("/api/refills/summary?location_id=1")
    assert summ.status_code == 200
    assert order_count(db_session) == before
    # 失败原因只能是不在补货时段，不得改写成满仓/无货道口径
    assert r.json()["detail"] == "不在补货时段"


def test_open_window_generates_and_summary_matches_new_order(client, db_session):
    # 放宽窗覆盖当前时刻
    client.frozen["at"] = datetime(2026, 10, 3, 3, 33)
    assert client.put("/api/locations/1", json={"fill_start_minute": 0, "fill_end_minute": 1439}).status_code == 200

    loc = db_session.get(Location, 1)
    assert client.get("/api/locations").json()[0]["fill_open"] is True

    r = client.post("/api/refills/run?location_id=1")
    assert r.status_code == 200
    new_order = r.json()

    summ = client.get("/api/refills/summary?location_id=1").json()
    for k in ("total_fill", "need_fill_count", "full_count", "overbooked_count"):
        assert summ[k] == new_order[k]
    # 新单与汇总来自同一张最近成功单
    latest = client.get("/api/refills/latest?location_id=1").json()
    assert latest["id"] == new_order["id"]


def test_half_open_boundary_decisions(client, db_session):
    client.put("/api/locations/1", json={"fill_start_minute": 600, "fill_end_minute": 660})

    client.frozen["at"] = datetime(2026, 10, 3, 10, 0)
    assert client.post("/api/refills/run?location_id=1").status_code == 200  # 起点在内

    client.frozen["at"] = datetime(2026, 10, 3, 11, 0)
    r = client.post("/api/refills/run?location_id=1")
    assert r.status_code == 403  # 终点分钟已在外
    assert r.json()["detail"] == "不在补货时段"


def test_invalid_window_rejected_and_unchanged(client, db_session):
    client.frozen["at"] = datetime(2026, 10, 3, 3, 33)
    # 先设合法窗
    client.put("/api/locations/1", json={"fill_start_minute": 600, "fill_end_minute": 660})
    before_orders = order_count(db_session)

    for bad in [
        {"fill_start_minute": 700, "fill_end_minute": 600},  # 结束不大于开始
        {"fill_start_minute": 600, "fill_end_minute": 600},  # 相等
        {"fill_start_minute": -1, "fill_end_minute": 100},   # 越下界
        {"fill_start_minute": 0, "fill_end_minute": 1440},   # 越上界
        {"fill_start_minute": 600, "fill_end_minute": None},# 只填一端
    ]:
        r = client.put("/api/locations/1", json=bad)
        assert r.status_code == 400
        db_session.expire_all()
        loc = db_session.get(Location, 1)
        assert (loc.fill_start_minute, loc.fill_end_minute) == (600, 660)  # 点位保持改前
        assert order_count(db_session) == before_orders                    # 单据保持改前


def test_clear_window_back_to_unrestricted(client, db_session):
    client.put("/api/locations/1", json={"fill_start_minute": 600, "fill_end_minute": 660})
    client.frozen["at"] = datetime(2026, 10, 3, 3, 33)
    assert client.post("/api/refills/run?location_id=1").status_code == 403
    # 双空清空 = 不限制，与现网随时可生成相同
    assert client.put("/api/locations/1", json={"fill_start_minute": None, "fill_end_minute": None}).status_code == 200
    assert client.post("/api/refills/run?location_id=1").status_code == 200
