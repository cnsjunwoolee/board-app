from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(50), nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan", order_by="Comment.created_at")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    author = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    post = relationship("Post", back_populates="comments")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    birth_date = Column(String(20))          # 예: 2008-03-15
    grade = Column(String(20))               # 예: 1학년, 2학년
    phone = Column(String(20))
    email = Column(String(100))
    photo_path = Column(String(200))         # static/uploads/파일명
    score = Column(Integer, default=0)       # 평가 점수
    memo = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class Notice(Base):
    __tablename__ = "notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text)                   # HTML 내용
    author = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class RecruitBanner(Base):
    __tablename__ = "recruit_banner"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text)                   # HTML 내용
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    name = Column(String(50), nullable=False)
    is_active = Column(Integer, default=1)      # 1=활성, 0=비활성
    created_at = Column(DateTime, default=datetime.now)

    permissions = relationship("OperatorPermission", back_populates="operator", cascade="all, delete-orphan")

    def has_permission(self, menu_code: str) -> bool:
        return any(p.menu_code == menu_code for p in self.permissions)


class OperatorPermission(Base):
    __tablename__ = "operator_permissions"
    __table_args__ = (UniqueConstraint("operator_id", "menu_code"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(Integer, ForeignKey("operators.id"), nullable=False)
    menu_code = Column(String(50), nullable=False)  # 'member', 'board', 'admin'

    operator = relationship("Operator", back_populates="permissions")
