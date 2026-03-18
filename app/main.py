from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from app.database import engine
from app.models import Base
from app.routes import router
from app.member_routes import member_router
from app.recruit_routes import recruit_router
from app.notice_routes import notice_router
from app.board_routes import board_router

DEPLOYED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

app = FastAPI(title="게시판")

BASE_DIR = Path(__file__).parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["deployed_at"] = DEPLOYED_AT

Path(BASE_DIR / "static/uploads").mkdir(exist_ok=True)

Base.metadata.create_all(bind=engine)

# 기존 DB에 새 컬럼이 없을 경우 자동 추가 (마이그레이션 대체)
from sqlalchemy import text, inspect
with engine.connect() as conn:
    db_url = str(engine.url)
    if db_url.startswith("sqlite"):
        # SQLite: PRAGMA로 컬럼 존재 여부 확인
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(posts)")).fetchall()]
        if "view_count" not in cols:
            conn.execute(text("ALTER TABLE posts ADD COLUMN view_count INTEGER DEFAULT 0 NOT NULL"))
            conn.commit()
    else:
        # PostgreSQL: IF NOT EXISTS 지원
        conn.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0 NOT NULL"))
        conn.commit()

app.include_router(router)
app.include_router(member_router)
app.include_router(recruit_router)
app.include_router(notice_router)
app.include_router(board_router)
