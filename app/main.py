from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.models import Base, Operator, OperatorPermission, Screen, MenuSection
from app.routes import router
from app.member_routes import member_router
from app.recruit_routes import recruit_router
from app.notice_routes import notice_router
from app.board_routes import board_router
from app.home_routes import home_router
from app.auth_routes import auth_router
from app.admin_routes import admin_router
from app.part_routes import part_router
from app.bom_routes import bom_router
from app.screen_routes import screen_router
from app.menu_routes import menu_router
from app.auth import get_current_operator, hash_password
import app.menu_cache as menu_cache

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

# BOM 테이블 새 컬럼 마이그레이션
with engine.connect() as conn:
    db_url = str(engine.url)
    try:
        if db_url.startswith("sqlite"):
            # bom_items: effective_start, effective_end
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(bom_items)")).fetchall()]
            if "effective_start" not in cols:
                conn.execute(text("ALTER TABLE bom_items ADD COLUMN effective_start VARCHAR(10)"))
                conn.execute(text("ALTER TABLE bom_items ADD COLUMN effective_end VARCHAR(10) DEFAULT '9999-12-31'"))
                conn.commit()
            # bom_headers: checked_out, version type change
            cols_h = [r[1] for r in conn.execute(text("PRAGMA table_info(bom_headers)")).fetchall()]
            if "checked_out" not in cols_h:
                conn.execute(text("ALTER TABLE bom_headers ADD COLUMN checked_out INTEGER DEFAULT 0"))
                conn.commit()
            if "checked_out_by" not in cols_h:
                conn.execute(text("ALTER TABLE bom_headers ADD COLUMN checked_out_by VARCHAR(50)"))
                conn.commit()
        else:
            conn.execute(text("ALTER TABLE bom_items ADD COLUMN IF NOT EXISTS effective_start VARCHAR(10)"))
            conn.execute(text("ALTER TABLE bom_items ADD COLUMN IF NOT EXISTS effective_end VARCHAR(10) DEFAULT '9999-12-31'"))
            conn.execute(text("ALTER TABLE bom_headers ADD COLUMN IF NOT EXISTS checked_out INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE bom_headers ADD COLUMN IF NOT EXISTS checked_out_by VARCHAR(50)"))
            conn.execute(text("ALTER TABLE bom_items ADD COLUMN IF NOT EXISTS creator VARCHAR(50)"))
            conn.execute(text("ALTER TABLE bom_items ADD COLUMN IF NOT EXISTS updater VARCHAR(50)"))
            # version 컬럼 타입 변경 (INTEGER → VARCHAR) - PLM 버전 형식 "1.0" 지원
            conn.execute(text("ALTER TABLE bom_headers ALTER COLUMN version TYPE VARCHAR(10) USING version::text"))
            conn.commit()
    except Exception:
        pass

# parent_item_id FK 제약 제거 (PLM 구조 변경으로 더이상 사용 안함)
with engine.connect() as conn:
    db_url = str(engine.url)
    try:
        if not db_url.startswith("sqlite"):
            # PostgreSQL: FK 제약 찾아서 DROP
            fk_rows = conn.execute(text("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'bom_items' AND constraint_type = 'FOREIGN KEY'
                AND constraint_name LIKE '%parent_item_id%'
            """)).fetchall()
            for row in fk_rows:
                conn.execute(text(f"ALTER TABLE bom_items DROP CONSTRAINT {row[0]}"))
            conn.commit()
    except Exception:
        pass

# ── screens 테이블 새 컬럼 마이그레이션 ────────────────────────────────────────
with engine.connect() as conn:
    db_url = str(engine.url)
    try:
        if db_url.startswith("sqlite"):
            cols = [r[1] for r in conn.execute(text("PRAGMA table_info(screens)")).fetchall()]
            if "show_in_menu" not in cols:
                conn.execute(text("ALTER TABLE screens ADD COLUMN show_in_menu INTEGER DEFAULT 0"))
                conn.commit()
        else:
            conn.execute(text("ALTER TABLE screens ADD COLUMN IF NOT EXISTS show_in_menu INTEGER DEFAULT 0"))
            conn.commit()
        # 기존 데이터에 show_in_menu 설정 (SQLite, PostgreSQL 공통)
        conn.execute(text("""
            UPDATE screens SET show_in_menu = 1
            WHERE screen_id IN ('SCR-MEM-LIST','SCR-REC-BANNER','SCR-BOARD-LIST',
                'SCR-NOTICE-LIST','SCR-PART-LIST','SCR-BOM-LIST',
                'SCR-ADMIN-OP','SCR-ADMIN-SCR','SCR-ADMIN-MENU')
            AND show_in_menu = 0
        """))
        conn.commit()
    except Exception:
        pass

# ── 화면(Screen) + 메뉴섹션(MenuSection) 시드 데이터 ──────────────────────────
from app.database import SessionLocal as _SL
_seed_db = _SL()
try:
    # 화면 시드 (screen_id, name, section, url, desc, order, perm, show_in_menu)
    if _seed_db.query(Screen).count() == 0:
        _screen_seeds = [
            ("SCR-HOME",         "홈",              "member", "/home",             "", 10,  "",      0),
            ("SCR-MEM-LIST",     "회원조회",        "member", "/members/",         "", 20,  "member",1),
            ("SCR-MEM-FORM",     "회원등록/수정",   "member", "/members/new",      "", 30,  "member",0),
            ("SCR-REC-BANNER",   "회원모집 배너",   "member", "/recruit/banner",   "", 40,  "member",1),
            ("SCR-BOARD-LIST",   "게시판 목록",     "board",  "/board/",           "", 10,  "board", 1),
            ("SCR-BOARD-DETAIL", "게시글 상세",     "board",  "/posts",            "", 15,  "board", 0),
            ("SCR-BOARD-FORM",   "게시글 작성",     "board",  "/board/new",        "", 20,  "board", 0),
            ("SCR-NOTICE-LIST",  "공지사항 목록",   "board",  "/notices/",         "", 30,  "board", 1),
            ("SCR-NOTICE-FORM",  "공지사항 작성",   "board",  "/notices/new",      "", 40,  "board", 0),
            ("SCR-PART-LIST",    "부품조회",        "bom",    "/bom/parts",        "", 10,  "",      1),
            ("SCR-PART-FORM",    "부품등록/수정",   "bom",    "/bom/parts/new",    "", 20,  "",      0),
            ("SCR-BOM-LIST",     "BOM 조회",        "bom",    "/bom/list",         "", 30,  "",      1),
            ("SCR-BOM-DETAIL",   "BOM 상세",        "bom",    "/bom/detail",       "", 40,  "",      0),
            ("SCR-BOM-EDIT",     "BOM 편집",        "bom",    "/bom/edit",         "", 50,  "",      0),
            ("SCR-ADMIN-OP",     "운영진 관리",     "admin",  "/admin/operators",  "", 10,  "admin", 1),
            ("SCR-ADMIN-SCR",    "화면 관리",       "admin",  "/admin/screens",    "", 20,  "admin", 1),
            ("SCR-ADMIN-MENU",   "메뉴 관리",       "admin",  "/admin/menus",      "", 30,  "admin", 1),
        ]
        for sid, name, section, url, desc, order, perm, show in _screen_seeds:
            _seed_db.add(Screen(
                screen_id=sid, name=name, section=section,
                url_pattern=url, description=desc, sort_order=order,
                required_permission=perm or None, show_in_menu=show,
            ))
        _seed_db.commit()
    else:
        # 기존 DB: 누락된 화면 추가
        _extra_screens = [
            ("SCR-BOARD-DETAIL", "게시글 상세",  "board", "/posts",        "", 15, "board", 0),
            ("SCR-ADMIN-MENU",   "메뉴 관리",    "admin", "/admin/menus",  "", 30, "admin", 1),
        ]
        for sid, name, section, url, desc, order, perm, show in _extra_screens:
            if not _seed_db.query(Screen).filter(Screen.screen_id == sid).first():
                _seed_db.add(Screen(
                    screen_id=sid, name=name, section=section,
                    url_pattern=url, description=desc, sort_order=order,
                    required_permission=perm or None, show_in_menu=show,
                ))
        _seed_db.commit()

    # 메뉴 섹션 시드
    if _seed_db.query(MenuSection).count() == 0:
        _section_seeds = [
            ("member", "회원모집", 10, ""),
            ("board",  "게시판",   20, ""),
            ("bom",    "BOM",      30, ""),
            ("admin",  "관리",     40, "admin"),
        ]
        for code, name, order, perm in _section_seeds:
            _seed_db.add(MenuSection(
                code=code, name=name, sort_order=order,
                required_permission=perm or None,
            ))
        _seed_db.commit()
except Exception:
    pass
finally:
    _seed_db.close()


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

# 화면 ID 매핑 (URL → screen_id) - 서버 시작 시 캐시
_screen_url_map = {}
try:
    _map_db = _SL()
    for s in _map_db.query(Screen).filter(Screen.is_active == 1).all():
        if s.url_pattern:
            _screen_url_map[s.url_pattern] = s.screen_id
    _map_db.close()
except Exception:
    pass

def _get_screen_id(request):
    """request의 URL path에서 매칭되는 screen_id 반환."""
    path = str(request.url.path)
    # 정확한 매칭 먼저
    if path in _screen_url_map:
        return _screen_url_map[path]
    # prefix 매칭 (긴 것부터)
    for url, sid in sorted(_screen_url_map.items(), key=lambda x: -len(x[0])):
        if path.startswith(url):
            return sid
    return None

templates.env.globals["get_screen_id"] = _get_screen_id

# 메뉴 캐시 초기화 & Jinja2 전역
menu_cache.init(_SL)
templates.env.globals["menu_sections"] = menu_cache.get_sections
templates.env.globals["menu_sidebar_items"] = menu_cache.get_sidebar_items
templates.env.globals["menu_url_section_map"] = menu_cache.get_url_section_map


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
app.include_router(part_router)
app.include_router(bom_router)
app.include_router(screen_router)
app.include_router(menu_router)
