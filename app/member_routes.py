from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.database import get_db
from app.models import Member

member_router = APIRouter(prefix="/members")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

UPLOAD_DIR = BASE_DIR / "static/uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# 1. GET /members/ - 회원 목록 (검색: 이름, 학년)
@member_router.get("/")
def list_members(
    request: Request,
    name: Optional[str] = None,
    grade: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Member)

    if name:
        query = query.filter(Member.name.contains(name))
    if grade:
        query = query.filter(Member.grade == grade)

    members = query.order_by(Member.created_at.desc()).all()

    return templates.TemplateResponse(
        "members/list.html",
        {
            "request": request,
            "members": members,
            "search_name": name or "",
            "search_grade": grade or "",
        },
    )


# 2. GET /members/new - 회원 등록 폼
@member_router.get("/new")
def new_member_form(request: Request):
    return templates.TemplateResponse(
        "members/form.html",
        {"request": request, "member": None},
    )


# 3. POST /members/ - 회원 등록 처리 (사진 업로드 포함)
@member_router.post("/")
async def create_member(
    request: Request,
    name: str = Form(...),
    birth_date: Optional[str] = Form(None),
    grade: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    score: Optional[int] = Form(None),
    memo: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    photo_path = None

    if photo and photo.filename:
        ext = Path(photo.filename).suffix
        unique_name = f"{uuid.uuid4().hex}_{photo.filename}"
        save_path = UPLOAD_DIR / unique_name
        content = await photo.read()
        with open(save_path, "wb") as f:
            f.write(content)
        photo_path = f"uploads/{unique_name}"

    member = Member(
        name=name,
        birth_date=birth_date or None,
        grade=grade or None,
        phone=phone or None,
        email=email or None,
        photo_path=photo_path,
        score=score if score is not None else 0,
        memo=memo or None,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return RedirectResponse(url=f"/members/{member.id}", status_code=303)


# 4. GET /members/{id} - 회원 상세
@member_router.get("/{member_id}")
def get_member(member_id: int, request: Request, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "members/detail.html",
        {"request": request, "member": member},
    )


# 5. GET /members/{id}/edit - 회원 수정 폼
@member_router.get("/{member_id}/edit")
def edit_member_form(member_id: int, request: Request, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "members/form.html",
        {"request": request, "member": member},
    )


# 6. POST /members/{id}/edit - 회원 수정 처리
@member_router.post("/{member_id}/edit")
async def update_member(
    member_id: int,
    request: Request,
    name: str = Form(...),
    birth_date: Optional[str] = Form(None),
    grade: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    score: Optional[int] = Form(None),
    memo: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")

    if photo and photo.filename:
        unique_name = f"{uuid.uuid4().hex}_{photo.filename}"
        save_path = UPLOAD_DIR / unique_name
        content = await photo.read()
        with open(save_path, "wb") as f:
            f.write(content)
        member.photo_path = f"uploads/{unique_name}"

    member.name = name
    member.birth_date = birth_date or None
    member.grade = grade or None
    member.phone = phone or None
    member.email = email or None
    member.score = score if score is not None else 0
    member.memo = memo or None

    db.commit()
    db.refresh(member)
    return RedirectResponse(url=f"/members/{member.id}", status_code=303)


# 7. POST /members/{id}/delete - 회원 삭제
@member_router.post("/{member_id}/delete")
def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(status_code=404, detail="회원을 찾을 수 없습니다.")
    db.delete(member)
    db.commit()
    return RedirectResponse(url="/members/", status_code=303)
