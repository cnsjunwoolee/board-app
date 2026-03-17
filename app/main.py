from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from app.database import engine
from app.models import Base
from app.routes import router

DEPLOYED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

app = FastAPI(title="게시판")

BASE_DIR = Path(__file__).parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["deployed_at"] = DEPLOYED_AT

Base.metadata.create_all(bind=engine)

# 기존 DB에 새 컬럼이 없을 경우 자동 추가 (마이그레이션 대체)
with engine.connect() as conn:
    from sqlalchemy import text
    conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0 NOT NULL"))
    conn.commit()

app.include_router(router)
