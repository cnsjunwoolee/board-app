from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
import math

from app.database import get_db
from app.models import Post

board_router = APIRouter(prefix="/board")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

PAGE_SIZE = 10


# GET /board/ - 게시글 목록 (페이지네이션)
@board_router.get("/")
def list_board(request: Request, page: int = 1, frame: bool = False, db: Session = Depends(get_db)):
    total = db.query(Post).count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages))
    posts = (
        db.query(Post)
        .order_by(Post.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    return templates.TemplateResponse(
        "board/list.html",
        {
            "request": request,
            "posts": posts,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "is_frame": frame,
        },
    )
