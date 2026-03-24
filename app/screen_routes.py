from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Screen, ScreenAuditLog
from app.auth import get_current_operator
import app.menu_cache as menu_cache

screen_router = APIRouter(prefix="/admin/screens", tags=["screen"])

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

SECTION_LABELS = {
    "member": "회원모집",
    "board": "게시판",
    "bom": "BOM",
    "admin": "관리",
}


def require_admin(request: Request, db: Session):
    op = get_current_operator(request, db)
    if not op or not op.has_permission("admin"):
        return None
    return op


def _log_audit(db: Session, screen: Screen, action: str, changed_by: str,
               field_name: str = None, old_value: str = None, new_value: str = None):
    db.add(ScreenAuditLog(
        screen_id=screen.id, action=action, field_name=field_name,
        old_value=old_value, new_value=new_value, changed_by=changed_by,
    ))


# ── 화면 목록 ──────────────────────────────────────────────────────────────────

@screen_router.get("")
def screen_list(request: Request, section: str = "", q: str = "",
                frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    query = db.query(Screen)
    if section:
        query = query.filter(Screen.section == section)
    if q:
        query = query.filter(
            (Screen.screen_id.ilike(f"%{q}%")) | (Screen.name.ilike(f"%{q}%"))
        )
    screens = query.order_by(Screen.section, Screen.sort_order, Screen.id).all()

    return templates.TemplateResponse("admin/screen_list.html", {
        "request": request, "screens": screens, "is_frame": frame,
        "section_labels": SECTION_LABELS, "current_section": section, "q": q,
    })


# ── 화면 등록/수정 폼 ─────────────────────────────────────────────────────────

@screen_router.get("/new")
def screen_new(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("admin/screen_form.html", {
        "request": request, "screen": None, "is_frame": frame,
        "section_labels": SECTION_LABELS, "error": "",
    })


@screen_router.get("/{scr_id}/edit")
def screen_edit(scr_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    screen = db.query(Screen).filter(Screen.id == scr_id).first()
    if not screen:
        return RedirectResponse(url="/admin/screens", status_code=303)
    return templates.TemplateResponse("admin/screen_form.html", {
        "request": request, "screen": screen, "is_frame": frame,
        "section_labels": SECTION_LABELS, "error": "",
    })


# ── 화면 저장 ──────────────────────────────────────────────────────────────────

@screen_router.post("")
def screen_create(
    request: Request,
    screen_id: str = Form(...),
    name: str = Form(...),
    section: str = Form(...),
    url_pattern: str = Form(default=""),
    description: str = Form(default=""),
    sort_order: int = Form(default=0),
    is_active: int = Form(default=1),
    show_in_menu: int = Form(default=0),
    required_permission: str = Form(default=""),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    if db.query(Screen).filter(Screen.screen_id == screen_id).first():
        return templates.TemplateResponse("admin/screen_form.html", {
            "request": request, "screen": None, "is_frame": False,
            "section_labels": SECTION_LABELS, "error": "이미 사용 중인 화면 ID입니다.",
        })

    scr = Screen(
        screen_id=screen_id, name=name, section=section,
        url_pattern=url_pattern, description=description,
        sort_order=sort_order, is_active=is_active,
        show_in_menu=show_in_menu,
        required_permission=required_permission or None,
    )
    db.add(scr)
    db.flush()
    _log_audit(db, scr, "CREATE", op.name)
    db.commit()
    menu_cache.refresh()
    return RedirectResponse(url="/admin/screens", status_code=303)


@screen_router.post("/{scr_id}/edit")
def screen_update(
    scr_id: int,
    request: Request,
    name: str = Form(...),
    section: str = Form(...),
    url_pattern: str = Form(default=""),
    description: str = Form(default=""),
    sort_order: int = Form(default=0),
    is_active: int = Form(default=1),
    show_in_menu: int = Form(default=0),
    required_permission: str = Form(default=""),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if not scr:
        return RedirectResponse(url="/admin/screens", status_code=303)

    # 변경 감지 & 감사 로그
    changes = {
        "name": (scr.name, name),
        "section": (scr.section, section),
        "url_pattern": (scr.url_pattern or "", url_pattern),
        "description": (scr.description or "", description),
        "sort_order": (str(scr.sort_order), str(sort_order)),
        "is_active": (str(scr.is_active), str(is_active)),
        "show_in_menu": (str(scr.show_in_menu), str(show_in_menu)),
        "required_permission": (scr.required_permission or "", required_permission),
    }
    for field, (old, new) in changes.items():
        if str(old) != str(new):
            _log_audit(db, scr, "UPDATE", op.name, field, str(old), str(new))

    scr.name = name
    scr.section = section
    scr.url_pattern = url_pattern
    scr.description = description
    scr.sort_order = sort_order
    scr.is_active = is_active
    scr.show_in_menu = show_in_menu
    scr.required_permission = required_permission or None
    db.commit()
    menu_cache.refresh()
    return RedirectResponse(url="/admin/screens", status_code=303)


# ── 화면 삭제 ──────────────────────────────────────────────────────────────────

@screen_router.post("/{scr_id}/delete")
def screen_delete(scr_id: int, request: Request, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if scr:
        _log_audit(db, scr, "DELETE", op.name, "screen_id", scr.screen_id, None)
        db.delete(scr)
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/screens", status_code=303)


# ── 변경 이력 ──────────────────────────────────────────────────────────────────

@screen_router.get("/{scr_id}/audit")
def screen_audit(scr_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if not scr:
        return RedirectResponse(url="/admin/screens", status_code=303)
    logs = db.query(ScreenAuditLog).filter(
        ScreenAuditLog.screen_id == scr_id
    ).order_by(ScreenAuditLog.created_at.desc()).all()
    return templates.TemplateResponse("admin/screen_audit.html", {
        "request": request, "screen": scr, "logs": logs, "is_frame": frame,
    })


# ── 순서 변경 (AJAX) ──────────────────────────────────────────────────────────

@screen_router.post("/{scr_id}/reorder")
def screen_reorder(scr_id: int, request: Request,
                   sort_order: int = Form(...), db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/admin/screens", status_code=303)
    scr = db.query(Screen).filter(Screen.id == scr_id).first()
    if scr:
        old = str(scr.sort_order)
        scr.sort_order = sort_order
        _log_audit(db, scr, "UPDATE", op.name, "sort_order", old, str(sort_order))
        db.commit()
        menu_cache.refresh()
    return RedirectResponse(url="/admin/screens", status_code=303)
