from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import Operator, OperatorPermission
from app.auth import get_current_operator, hash_password, MENU_LABELS

admin_router = APIRouter(prefix="/admin", tags=["admin"])

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def require_admin(request: Request, db: Session):
    """관리 권한 필수. 미로그인 또는 권한 없으면 None."""
    op = get_current_operator(request, db)
    if not op:
        return None
    if not op.has_permission("admin"):
        return None
    return op


@admin_router.get("/operators")
def operator_list(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    operators = db.query(Operator).order_by(Operator.id).all()
    return templates.TemplateResponse("admin/operator_list.html", {
        "request": request, "operators": operators, "current_op": op,
        "is_frame": frame, "menu_labels": MENU_LABELS,
    })


@admin_router.get("/operators/new")
def operator_new(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("admin/operator_form.html", {
        "request": request, "operator": None, "is_frame": frame,
        "menu_labels": MENU_LABELS, "error": "",
    })


@admin_router.post("/operators")
def operator_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    permissions: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    # 중복 체크
    if db.query(Operator).filter(Operator.username == username).first():
        return templates.TemplateResponse("admin/operator_form.html", {
            "request": request, "operator": None, "is_frame": False,
            "menu_labels": MENU_LABELS, "error": "이미 사용 중인 아이디입니다.",
        })

    new_op = Operator(
        username=username,
        password_hash=hash_password(password),
        name=name,
    )
    db.add(new_op)
    db.flush()

    for code in permissions:
        if code in MENU_LABELS:
            db.add(OperatorPermission(operator_id=new_op.id, menu_code=code))
    db.commit()
    return RedirectResponse(url="/admin/operators", status_code=303)


@admin_router.get("/operators/{op_id}/edit")
def operator_edit(op_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    target = db.query(Operator).filter(Operator.id == op_id).first()
    if not target:
        return RedirectResponse(url="/admin/operators", status_code=303)
    return templates.TemplateResponse("admin/operator_form.html", {
        "request": request, "operator": target, "is_frame": frame,
        "menu_labels": MENU_LABELS, "error": "",
    })


@admin_router.post("/operators/{op_id}/edit")
def operator_update(
    op_id: int,
    request: Request,
    name: str = Form(...),
    password: str = Form(default=""),
    is_active: int = Form(default=1),
    permissions: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    target = db.query(Operator).filter(Operator.id == op_id).first()
    if not target:
        return RedirectResponse(url="/admin/operators", status_code=303)

    target.name = name
    target.is_active = is_active
    if password.strip():
        target.password_hash = hash_password(password.strip())

    # 권한 갱신
    db.query(OperatorPermission).filter(OperatorPermission.operator_id == op_id).delete()
    for code in permissions:
        if code in MENU_LABELS:
            db.add(OperatorPermission(operator_id=op_id, menu_code=code))
    db.commit()
    return RedirectResponse(url="/admin/operators", status_code=303)


@admin_router.post("/operators/{op_id}/delete")
def operator_delete(op_id: int, request: Request, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    # 자기 자신 삭제 방지
    if op.id == op_id:
        return RedirectResponse(url="/admin/operators", status_code=303)

    target = db.query(Operator).filter(Operator.id == op_id).first()
    if target:
        db.delete(target)
        db.commit()
    return RedirectResponse(url="/admin/operators", status_code=303)
