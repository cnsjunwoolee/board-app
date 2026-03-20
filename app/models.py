from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, UniqueConstraint
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


# ── BOM 관리 모델 ──────────────────────────────────────────────────────────────

class Part(Base):
    __tablename__ = "parts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_number = Column(String(20), unique=True, nullable=False)
    description = Column(String(200), nullable=False)
    spec = Column(String(200), nullable=False)
    category = Column(String(30))       # '모델', '반제품', '기구자재', '회로자재', '기타'
    unit = Column(String(20))           # 'EA', 'KG', 'M', 'SET' 등
    weight = Column(String(20))         # 중량
    material = Column(String(100))      # 재질
    manufacturer = Column(String(100))  # 제조사
    lead_time = Column(Integer)         # 리드타임(일)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class BOMHeader(Base):
    __tablename__ = "bom_headers"
    __table_args__ = (UniqueConstraint("part_id", "bom_type", "version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    bom_type = Column(String(10), nullable=False)   # 'E-BOM', 'M-BOM', 'S-BOM'
    version = Column(String(10), default="1.0")    # Major.Iteration (1.0, 1.1, 2.0...)
    effective_date = Column(String(10))             # 'YYYY-MM-DD'
    status = Column(String(20), default="작성중")   # '작성중', '체크아웃', '승인', '폐기'
    checked_out = Column(Integer, default=0)        # 0=체크인, 1=체크아웃
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    items = relationship("BOMItem", back_populates="bom_header", cascade="all, delete-orphan")
    part = relationship("Part")


class BOMItem(Base):
    __tablename__ = "bom_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_id = Column(Integer, ForeignKey("bom_headers.id"), nullable=False)
    parent_item_id = Column(Integer, ForeignKey("bom_items.id"), nullable=True)  # null이면 최상위 직속 자식
    child_part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String(20), default="EA")
    seq_no = Column(Integer, default=0)     # 정렬 순서
    effective_start = Column(String(10))    # 적용시작일 'YYYY-MM-DD'
    effective_end = Column(String(10), default="9999-12-31")  # 적용종료일
    remark = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)

    child_part = relationship("Part")
    parent_item = relationship("BOMItem", back_populates="children", remote_side="BOMItem.id")
    children = relationship("BOMItem", back_populates="parent_item", cascade="all, delete-orphan")
    substitutes = relationship("BOMSubstitute", back_populates="bom_item", cascade="all, delete-orphan")
    bom_header = relationship("BOMHeader", back_populates="items")


class BOMSubstitute(Base):
    __tablename__ = "bom_substitutes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_item_id = Column(Integer, ForeignKey("bom_items.id"), nullable=False)
    substitute_part_id = Column(Integer, ForeignKey("parts.id"), nullable=False)
    priority = Column(Integer, default=1)
    remark = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)

    bom_item = relationship("BOMItem", back_populates="substitutes")
    substitute_part = relationship("Part")
