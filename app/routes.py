from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
import math

from app.database import get_db
from app.models import Post, Comment

router = APIRouter()

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

PAGE_SIZE = 10


# 1. GET /posts/ - 게시글 목록 (페이지네이션)
@router.get("/posts/")
def list_posts(request: Request, page: int = 1, frame: bool = False, db: Session = Depends(get_db)):
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
        "index.html",
        {"request": request, "posts": posts, "page": page, "total_pages": total_pages, "total": total, "is_frame": frame},
    )


# 2. GET /posts/new - 게시글 작성 폼
@router.get("/posts/new")
def new_post_form(request: Request, frame: bool = False):
    return templates.TemplateResponse("post_form.html", {"request": request, "post": None, "is_frame": frame})


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


# 4. GET /posts/{post_id} - 게시글 상세보기 (조회수 증가)
@router.get("/posts/{post_id}")
def get_post(post_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    post.view_count += 1
    db.commit()
    db.refresh(post)
    return templates.TemplateResponse("post_detail.html", {"request": request, "post": post, "is_frame": frame})


# 5. GET /posts/{post_id}/edit - 게시글 수정 폼
@router.get("/posts/{post_id}/edit")
def edit_post_form(post_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return templates.TemplateResponse("post_form.html", {"request": request, "post": post, "is_frame": frame})


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


# 8. POST /posts/{post_id}/comments - 댓글 작성
@router.post("/posts/{post_id}/comments")
def create_comment(
    post_id: int,
    author: str = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    post = db.query(Post).filter(Post.id == post_id).first()
    if post is None:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    comment = Comment(post_id=post_id, author=author, content=content)
    db.add(comment)
    db.commit()
    return RedirectResponse(url=f"/posts/{post_id}#comments", status_code=303)


# 9. POST /posts/{post_id}/comments/{comment_id}/delete - 댓글 삭제
@router.post("/posts/{post_id}/comments/{comment_id}/delete")
def delete_comment(post_id: int, comment_id: int, db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.post_id == post_id).first()
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    db.delete(comment)
    db.commit()
    return RedirectResponse(url=f"/posts/{post_id}#comments", status_code=303)
