from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Post

router = APIRouter()

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# 1. GET / - 게시글 목록 (최신순 정렬)
@router.get("/")
def list_posts(request: Request, db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "posts": posts},
    )


# 2. GET /posts/new - 게시글 작성 폼
@router.get("/posts/new")
def new_post_form(request: Request):
    return templates.TemplateResponse(
        "post_form.html",
        {"request": request, "post": None},
    )


# 3. POST /posts - 게시글 저장
@router.post("/posts")
def create_post(
    title: str = Form(...),
    content: str = Form(...),
    author: str = Form(...),
    db: Session = Depends(get_db),
):
    post = Post(title=title, content=content, author=author)
    db.add(post)
    db.commit()
    db.refresh(post)
    return RedirectResponse(url=f"/posts/{post.id}", status_code=303)


# 4. GET /posts/{post_id} - 게시글 상세보기
@router.get("/posts/{post_id}")
def get_post(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "post_detail.html",
        {"request": request, "post": post},
    )


# 5. GET /posts/{post_id}/edit - 게시글 수정 폼
@router.get("/posts/{post_id}/edit")
def edit_post_form(post_id: int, request: Request, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "post_form.html",
        {"request": request, "post": post},
    )


# 6. POST /posts/{post_id}/edit - 게시글 수정 처리
@router.post("/posts/{post_id}/edit")
def update_post(
    post_id: int,
    title: str = Form(...),
    content: str = Form(...),
    author: str = Form(...),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    post.title = title
    post.content = content
    post.author = author
    db.commit()
    db.refresh(post)
    return RedirectResponse(url=f"/posts/{post.id}", status_code=303)


# 7. POST /posts/{post_id}/delete - 게시글 삭제
@router.post("/posts/{post_id}/delete")
def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    db.delete(post)
    db.commit()
    return RedirectResponse(url="/", status_code=303)
