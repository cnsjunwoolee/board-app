from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models import RecruitBanner

recruit_router = APIRouter(prefix="/recruit")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# 1. GET /recruit/banner - 배너 편집 화면
@recruit_router.get("/banner")
def banner_editor(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    banner = db.query(RecruitBanner).first()
    return templates.TemplateResponse(
        "members/banner_editor.html",
        {"request": request, "banner": banner, "is_frame": frame},
    )


# 2. POST /recruit/banner - 배너 저장 (upsert)
@recruit_router.post("/banner")
def save_banner(
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    banner = db.query(RecruitBanner).first()
    if banner:
        banner.content = content
        banner.updated_at = datetime.now()
    else:
        banner = RecruitBanner(content=content)
        db.add(banner)
    db.commit()
    return RedirectResponse(url="/recruit/banner", status_code=303)


# 3. GET /recruit/banner/view - 배너 미리보기
@recruit_router.get("/banner/view")
def banner_view(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    banner = db.query(RecruitBanner).first()
    return templates.TemplateResponse(
        "recruit/banner_view.html",
        {"request": request, "banner": banner, "is_frame": frame},
    )
