from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.models import Base, Operator, OperatorPermission
from app.routes import router
from app.member_routes import member_router
from app.recruit_routes import recruit_router
from app.notice_routes import notice_router
from app.board_routes import board_router
from app.home_routes import home_router
from app.auth_routes import auth_router
from app.admin_routes import admin_router
from app.auth import get_current_operator, hash_password

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

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """모든 요청에 current_operator를 request.state에 주입."""
    db = SessionLocal()
    try:
        request.state.current_operator = get_current_operator(request, db)
    except Exception:
        request.state.current_operator = None
    finally:
        db.close()
    response = await call_next(request)
    return response

# Jinja2 전역에서 request.state.current_operator 접근 가능하게
templates.env.globals["get_operator"] = lambda request: getattr(getattr(request, 'state', None), 'current_operator', None)


@app.get("/")
def shell(request: Request):
    return templates.TemplateResponse("base.html", {
        "request": request,
        "current_operator": request.state.current_operator,
    })


# 기본 관리자 계정 생성 (최초 실행 시)
from app.database import SessionLocal
_init_db = SessionLocal()
if not _init_db.query(Operator).filter(Operator.username == "admin").first():
    admin = Operator(username="admin", password_hash=hash_password("admin1234"), name="관리자")
    _init_db.add(admin)
    _init_db.flush()
    for code in ("member", "board", "admin"):
        _init_db.add(OperatorPermission(operator_id=admin.id, menu_code=code))
    _init_db.commit()
_init_db.close()


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(home_router)
app.include_router(router)
app.include_router(member_router)
app.include_router(recruit_router)
app.include_router(notice_router)
app.include_router(board_router)
