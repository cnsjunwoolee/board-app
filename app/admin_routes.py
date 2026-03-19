from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List
import random
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Operator, OperatorPermission, Member
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


@admin_router.post("/seed-members")
def seed_members(request: Request, db: Session = Depends(get_db)):
    """가상 회원 100명 생성 (운영 서버용)."""
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    last_names = ['김','이','박','최','정','강','조','윤','장','임','한','오','서','신','권','황','안','송','류','전']
    first_names = ['민준','서준','도윤','예준','시우','하준','주원','지호','지후','준서',
                   '서연','서윤','지우','하은','하윤','민서','지유','윤서','채원','수아',
                   '현우','지훈','건우','우진','선우','민재','현준','태윤','재윤','승현',
                   '소율','다은','예은','수빈','지아','채은','예린','지윤','나은','유진']
    grades = ['1학년','2학년','3학년']
    memos = ['열정적인 학생','프로그래밍에 관심이 많음','회로 설계를 좋아함','아두이노 프로젝트 경험',
             '3D 프린팅 경험 있음','대회 참가 경험','팀 리더 경험','성실한 학생','창의적인 아이디어가 많음',None]

    for i in range(100):
        name = random.choice(last_names) + random.choice(first_names)
        birth = datetime(2007 + random.randint(0, 2), random.randint(1, 12), random.randint(1, 28))
        m = Member(
            name=name,
            birth_date=birth.strftime('%Y-%m-%d'),
            grade=random.choice(grades),
            phone=f'010-{random.randint(1000,9999)}-{random.randint(1000,9999)}',
            email=f'student{i+1}@daeshin.hs.kr',
            score=random.randint(0, 5),
            memo=random.choice(memos),
            created_at=datetime.now() - timedelta(days=random.randint(0, 90)),
        )
        db.add(m)
    db.commit()
    return RedirectResponse(url="/members/", status_code=303)
