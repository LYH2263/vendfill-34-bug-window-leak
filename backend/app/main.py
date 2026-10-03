from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.seed import seed_if_empty


def ensure_schema() -> None:
    """create_all 只建新表，不给旧表补列；对既有 locations 表补时段窗列。"""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "locations" not in inspector.get_table_names():
        return
    existing = {c["name"] for c in inspector.get_columns("locations")}
    missing = [c for c in ("fill_start_minute", "fill_end_minute") if c not in existing]
    if missing:
        with engine.begin() as conn:
            for col in missing:
                conn.execute(text(f"ALTER TABLE locations ADD COLUMN {col} INTEGER"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="VendFill", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
