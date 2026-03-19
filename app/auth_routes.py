from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Operator
from app.auth import verify_password, create_session_token

auth_router = APIRouter(prefix="/auth", tags=["auth"])

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@auth_router.get("/login")
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@auth_router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    operator = db.query(Operator).filter(Operator.username == username, Operator.is_active == 1).first()
    if not operator or not verify_password(password, operator.password_hash):
        return templates.TemplateResponse("login.html", {
            "request": request, "error": "아이디 또는 비밀번호가 올바르지 않습니다."
        })

    token = create_session_token(operator.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("session", token, httponly=True, max_age=60 * 60 * 24 * 7)  # 7일
    return response


@auth_router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie("session")
    return response
