from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notice

notice_router = APIRouter(prefix="/notices")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# 1. GET /notices/ - 공지사항 목록 (최신순)
@notice_router.get("/")
def list_notices(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    notices = db.query(Notice).order_by(Notice.created_at.desc()).all()
    return templates.TemplateResponse(
        "notices/list.html",
        {"request": request, "notices": notices, "is_frame": frame},
    )


# 2. GET /notices/new - 공지사항 작성 폼
@notice_router.get("/new")
def new_notice_form(request: Request, frame: bool = False):
    return templates.TemplateResponse(
        "notices/form.html",
        {"request": request, "notice": None, "is_frame": frame},
    )


# 3. POST /notices/ - 공지사항 저장
@notice_router.post("/")
def create_notice(
    title: str = Form(...),
    author: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    notice = Notice(title=title, author=author, content=content)
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return RedirectResponse(url=f"/notices/{notice.id}", status_code=303)


# 4. GET /notices/{id} - 공지사항 상세
@notice_router.get("/{notice_id}")
def get_notice(notice_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "notices/detail.html",
        {"request": request, "notice": notice, "is_frame": frame},
    )


# 5. GET /notices/{id}/edit - 공지사항 수정 폼
@notice_router.get("/{notice_id}/edit")
def edit_notice_form(notice_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "notices/form.html",
        {"request": request, "notice": notice, "is_frame": frame},
    )


# 6. POST /notices/{id}/edit - 공지사항 수정 처리
@notice_router.post("/{notice_id}/edit")
def update_notice(
    notice_id: int,
    title: str = Form(...),
    author: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    notice.title = title
    notice.author = author
    notice.content = content
    db.commit()
    db.refresh(notice)
    return RedirectResponse(url=f"/notices/{notice.id}", status_code=303)


# 7. POST /notices/{id}/delete - 공지사항 삭제
@notice_router.post("/{notice_id}/delete")
def delete_notice(notice_id: int, db: Session = Depends(get_db)):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다.")
    db.delete(notice)
    db.commit()
    return RedirectResponse(url="/notices/", status_code=303)
