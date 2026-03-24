from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MenuSection, Screen
from app.auth import get_current_operator, MENU_LABELS
import app.menu_cache as menu_cache

menu_router = APIRouter(prefix="/admin/menus", tags=["menu"])

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def require_admin(request: Request, db: Session):
    op = get_current_operator(request, db)
    if not op or not op.has_permission("admin"):
        return None
    return op


# ── 메뉴 관리 목록 ────────────────────────────────────────────────────────────

@menu_router.get("")
def menu_list(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    sections = db.query(MenuSection).order_by(MenuSection.sort_order, MenuSection.id).all()

    screens_by_section = {}
    for sec in sections:
        items = (
            db.query(Screen)
            .filter(Screen.section == sec.code)
            .order_by(Screen.sort_order, Screen.id)
            .all()
        )
        screens_by_section[sec.code] = items

    return templates.TemplateResponse("admin/menu_list.html", {
        "request": request, "sections": sections,
        "screens_by_section": screens_by_section,
        "is_frame": frame, "menu_labels": MENU_LABELS,
    })


# ── 섹션 CRUD ─────────────────────────────────────────────────────────────────

@menu_router.get("/section/new")
def section_new(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("admin/menu_section_form.html", {
        "request": request, "section": None, "is_frame": frame,
        "menu_labels": MENU_LABELS, "error": "",
    })


@menu_router.post("/section")
def section_create(
    request: Request,
    code: str = Form(...),
    name: str = Form(...),
    sort_order: int = Form(default=0),
    required_permission: str = Form(default=""),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    if db.query(MenuSection).filter(MenuSection.code == code).first():
        return templates.TemplateResponse("admin/menu_section_form.html", {
            "request": request, "section": None, "is_frame": False,
            "menu_labels": MENU_LABELS, "error": "이미 사용 중인 코드입니다.",
        })
    sec = MenuSection(
        code=code, name=name, sort_order=sort_order,
        required_permission=required_permission or None,
    )
    db.add(sec)
    db.commit()
    menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


@menu_router.get("/section/{sec_id}/edit")
def section_edit(sec_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    sec = db.query(MenuSection).filter(MenuSection.id == sec_id).first()
    if not sec:
        return RedirectResponse(url="/admin/menus", status_code=303)
    return templates.TemplateResponse("admin/menu_section_form.html", {
        "request": request, "section": sec, "is_frame": frame,
        "menu_labels": MENU_LABELS, "error": "",
    })


@menu_router.post("/section/{sec_id}/edit")
def section_update(
    sec_id: int, request: Request,
    name: str = Form(...),
    sort_order: int = Form(default=0),
    is_active: int = Form(default=1),
    required_permission: str = Form(default=""),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    sec = db.query(MenuSection).filter(MenuSection.id == sec_id).first()
    if not sec:
        return RedirectResponse(url="/admin/menus", status_code=303)
    sec.name = name
    sec.sort_order = sort_order
    sec.is_active = is_active
    sec.required_permission = required_permission or None
    db.commit()
    menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


@menu_router.post("/section/{sec_id}/delete")
def section_delete(sec_id: int, request: Request, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    sec = db.query(MenuSection).filter(MenuSection.id == sec_id).first()
    if sec:
        db.delete(sec)
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


@menu_router.post("/section/{sec_id}/toggle")
def section_toggle(sec_id: int, request: Request, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/admin/menus", status_code=303)
    sec = db.query(MenuSection).filter(MenuSection.id == sec_id).first()
    if sec:
        sec.is_active = 0 if sec.is_active else 1
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


@menu_router.post("/section/{sec_id}/reorder")
def section_reorder(sec_id: int, request: Request, sort_order: int = Form(...),
                    db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/admin/menus", status_code=303)
    sec = db.query(MenuSection).filter(MenuSection.id == sec_id).first()
    if sec:
        sec.sort_order = sort_order
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


# ── 사이드바 아이템 (Screen) 메뉴 관련 토글/순서 ──────────────────────────────

@menu_router.post("/screen/{scr_id}/toggle-menu")
def screen_toggle_menu(scr_id: int, request: Request, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/admin/menus", status_code=303)
    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if scr:
        scr.show_in_menu = 0 if scr.show_in_menu else 1
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


@menu_router.post("/screen/{scr_id}/reorder")
def screen_reorder(scr_id: int, request: Request, sort_order: int = Form(...),
                   db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/admin/menus", status_code=303)
    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if scr:
        scr.sort_order = sort_order
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)


@menu_router.post("/screen/{scr_id}/update-permission")
def screen_update_permission(scr_id: int, request: Request,
                             required_permission: str = Form(default=""),
                             db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/admin/menus", status_code=303)
    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if scr:
        scr.required_permission = required_permission or None
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/menus", status_code=303)
