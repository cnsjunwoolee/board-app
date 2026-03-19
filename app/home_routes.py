from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Post, Notice

home_router = APIRouter()
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@home_router.get("/home")
def home(request: Request, db: Session = Depends(get_db)):
    recent_notices = db.query(Notice).order_by(Notice.created_at.desc()).limit(5).all()
    recent_posts = db.query(Post).order_by(Post.created_at.desc()).limit(5).all()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "recent_notices": recent_notices,
        "recent_posts": recent_posts,
    })
