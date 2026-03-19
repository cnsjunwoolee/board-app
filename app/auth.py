import hashlib
import hmac
import os
from fastapi import Request, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Operator

SECRET_KEY = os.environ.get("SESSION_SECRET", "act-club-session-secret-2024")

MENU_LABELS = {
    "member": "회원모집",
    "board": "게시판",
    "admin": "관리",
}


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, hashed = password_hash.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False


def create_session_token(operator_id: int) -> str:
    """operator_id를 서명하여 토큰 생성: id.signature"""
    msg = str(operator_id)
    sig = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{msg}.{sig}"


def parse_session_token(token: str):
    """토큰에서 operator_id 추출. 위변조 시 None 반환."""
    try:
        msg, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        return int(msg)
    except Exception:
        return None


def get_current_operator(request: Request, db=None):
    """현재 로그인한 운영진 반환. 미로그인 시 None."""
    token = request.cookies.get("session")
    if not token:
        return None
    operator_id = parse_session_token(token)
    if not operator_id:
        return None
    if db is None:
        return None
    return db.query(Operator).filter(Operator.id == operator_id, Operator.is_active == 1).first()
