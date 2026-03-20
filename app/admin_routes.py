from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List
import random
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Operator, OperatorPermission, Member, Part, BOMHeader, BOMItem, BOMSubstitute
from app.auth import get_current_operator, hash_password, MENU_LABELS

admin_router = APIRouter(prefix="/admin", tags=["admin"])

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def require_admin(request: Request, db: Session):
    """관리 권한 필수. 미로그인 또는 권한 없으면 None."""
    op = get_current_operator(request, db)
    if not op:
        return None
    if not op.has_permission("admin"):
        return None
    return op


@admin_router.get("/operators")
def operator_list(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    operators = db.query(Operator).order_by(Operator.id).all()
    return templates.TemplateResponse("admin/operator_list.html", {
        "request": request, "operators": operators, "current_op": op,
        "is_frame": frame, "menu_labels": MENU_LABELS,
    })


@admin_router.get("/operators/new")
def operator_new(request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse("admin/operator_form.html", {
        "request": request, "operator": None, "is_frame": frame,
        "menu_labels": MENU_LABELS, "error": "",
    })


@admin_router.post("/operators")
def operator_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    permissions: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    # 중복 체크
    if db.query(Operator).filter(Operator.username == username).first():
        return templates.TemplateResponse("admin/operator_form.html", {
            "request": request, "operator": None, "is_frame": False,
            "menu_labels": MENU_LABELS, "error": "이미 사용 중인 아이디입니다.",
        })

    new_op = Operator(
        username=username,
        password_hash=hash_password(password),
        name=name,
    )
    db.add(new_op)
    db.flush()

    for code in permissions:
        if code in MENU_LABELS:
            db.add(OperatorPermission(operator_id=new_op.id, menu_code=code))
    db.commit()
    return RedirectResponse(url="/admin/operators", status_code=303)


@admin_router.get("/operators/{op_id}/edit")
def operator_edit(op_id: int, request: Request, frame: bool = False, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)
    target = db.query(Operator).filter(Operator.id == op_id).first()
    if not target:
        return RedirectResponse(url="/admin/operators", status_code=303)
    return templates.TemplateResponse("admin/operator_form.html", {
        "request": request, "operator": target, "is_frame": frame,
        "menu_labels": MENU_LABELS, "error": "",
    })


@admin_router.post("/operators/{op_id}/edit")
def operator_update(
    op_id: int,
    request: Request,
    name: str = Form(...),
    password: str = Form(default=""),
    is_active: int = Form(default=1),
    permissions: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    target = db.query(Operator).filter(Operator.id == op_id).first()
    if not target:
        return RedirectResponse(url="/admin/operators", status_code=303)

    target.name = name
    target.is_active = is_active
    if password.strip():
        target.password_hash = hash_password(password.strip())

    # 권한 갱신
    db.query(OperatorPermission).filter(OperatorPermission.operator_id == op_id).delete()
    for code in permissions:
        if code in MENU_LABELS:
            db.add(OperatorPermission(operator_id=op_id, menu_code=code))
    db.commit()
    return RedirectResponse(url="/admin/operators", status_code=303)


@admin_router.post("/operators/{op_id}/delete")
def operator_delete(op_id: int, request: Request, db: Session = Depends(get_db)):
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    # 자기 자신 삭제 방지
    if op.id == op_id:
        return RedirectResponse(url="/admin/operators", status_code=303)

    target = db.query(Operator).filter(Operator.id == op_id).first()
    if target:
        db.delete(target)
        db.commit()
    return RedirectResponse(url="/admin/operators", status_code=303)


@admin_router.post("/sanitize-members")
def sanitize_members(request: Request, db: Session = Depends(get_db)):
    """회원 개인정보 일괄 변경 (전화번호, 이메일)."""
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    members = db.query(Member).all()
    for m in members:
        m.phone = "010-1111-1111"
        m.email = "test@test.co.kr"
    db.commit()
    return RedirectResponse(url="/members/", status_code=303)


@admin_router.post("/seed-members")
def seed_members(request: Request, db: Session = Depends(get_db)):
    """가상 회원 100명 생성 (운영 서버용)."""
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    last_names = ['김','이','박','최','정','강','조','윤','장','임','한','오','서','신','권','황','안','송','류','전']
    first_names = ['민준','서준','도윤','예준','시우','하준','주원','지호','지후','준서',
                   '서연','서윤','지우','하은','하윤','민서','지유','윤서','채원','수아',
                   '현우','지훈','건우','우진','선우','민재','현준','태윤','재윤','승현',
                   '소율','다은','예은','수빈','지아','채은','예린','지윤','나은','유진']
    grades = ['1학년','2학년','3학년']
    memos = ['열정적인 학생','프로그래밍에 관심이 많음','회로 설계를 좋아함','아두이노 프로젝트 경험',
             '3D 프린팅 경험 있음','대회 참가 경험','팀 리더 경험','성실한 학생','창의적인 아이디어가 많음',None]

    for i in range(100):
        name = random.choice(last_names) + random.choice(first_names)
        birth = datetime(2007 + random.randint(0, 2), random.randint(1, 12), random.randint(1, 28))
        m = Member(
            name=name,
            birth_date=birth.strftime('%Y-%m-%d'),
            grade=random.choice(grades),
            phone=f'010-{random.randint(1000,9999)}-{random.randint(1000,9999)}',
            email=f'student{i+1}@daeshin.hs.kr',
            score=random.randint(0, 5),
            memo=random.choice(memos),
            created_at=datetime.now() - timedelta(days=random.randint(0, 90)),
        )
        db.add(m)
    db.commit()
    return RedirectResponse(url="/members/", status_code=303)


@admin_router.post("/seed-bom")
def seed_bom(request: Request, db: Session = Depends(get_db)):
    """가상 부품 2000개 + BOM 구조 생성."""
    op = require_admin(request, db)
    if not op:
        return RedirectResponse(url="/auth/login", status_code=303)

    # 기존 부품 수를 오프셋으로 사용 (매번 추가 생성)
    offset = db.query(Part).count()

    descriptions_model = ['세탁기 모델', '냉장고 모델', '에어컨 모델', '전자레인지 모델', 'TV 모델',
                          '건조기 모델', '식기세척기 모델', '공기청정기 모델', '로봇청소기 모델', '스타일러 모델']
    descriptions_semi = ["메인보드 ASS'Y", '디스플레이 모듈', '컴프레서 유닛', '제어보드', '전원보드',
                         "히터 ASS'Y", "팬 모터 ASS'Y", "도어 ASS'Y", "필터 ASS'Y", '센서모듈']
    descriptions_mech = ['브라켓', '하우징', '커버', '패널', '프레임', '가스켓', '나사', '볼트', '너트',
                         '와셔', '스프링', '베어링', '기어', '샤프트', '캠']
    descriptions_elec = ['저항', '콘덴서', '트랜지스터', 'IC칩', 'LED', '다이오드', '릴레이', '퓨즈',
                         '커넥터', '케이블', 'PCB', '변압기', '센서', '스위치', '모터']
    descriptions_misc = ['라벨', '포장재', '매뉴얼', '스티커', '테이프', '접착제', '윤활유', '실리콘', '패킹', '절연체']

    specs_mech = ['SUS304', 'AL6061', 'PP', 'ABS', 'PC', 'PE', 'STEEL', 'ZINC', 'COPPER', 'NYLON']
    specs_elec = ['1/4W 10K', '0.1uF 50V', '2N2222', 'NE555', '5mm RED', '1N4148', '5V DC', '250V 1A', '2.54mm', 'AWG24']

    units = ['EA', 'EA', 'EA', 'KG', 'M', 'SET', 'L']
    manufacturers = ['삼성전기', 'LG이노텍', '대한전선', '서울반도체', 'LS전선', '풍산', '포스코', '현대제철', 'SK하이닉스', '일진전기']
    materials = ['SUS304', 'AL6061', 'ABS', 'PP', 'PC', 'COPPER', 'STEEL', 'RUBBER', 'GLASS', 'CERAMIC']

    # ── 부품 생성 ──────────────────────────────────────────────────────────────

    # 모델 20개
    model_parts = []
    for i in range(1, 21):
        n = offset + i
        p = Part(
            part_number=f'MODELA-{n:04d}AA',
            description=random.choice(descriptions_model) + f' {i}',
            spec=f'REV{i:02d}',
            category='모델',
            unit='EA',
            weight=str(round(random.uniform(5.0, 80.0), 1)),
            material=random.choice(materials),
            manufacturer=random.choice(manufacturers),
            lead_time=random.randint(30, 90),
        )
        db.add(p)
        model_parts.append(p)
    db.flush()

    # 반제품 200개
    semi_parts = []
    for i in range(1, 201):
        n = offset + i
        p = Part(
            part_number=f'SEMI{n:05d}A',
            description=random.choice(descriptions_semi),
            spec=f'VER{i:03d}',
            category='반제품',
            unit='EA',
            weight=str(round(random.uniform(0.5, 10.0), 2)),
            material=random.choice(materials),
            manufacturer=random.choice(manufacturers),
            lead_time=random.randint(14, 60),
        )
        db.add(p)
        semi_parts.append(p)
    db.flush()

    # 기구자재 600개
    mech_parts = []
    for i in range(1, 601):
        n = offset + i
        p = Part(
            part_number=f'MECH{n:05d}A',
            description=random.choice(descriptions_mech),
            spec=random.choice(specs_mech),
            category='기구자재',
            unit=random.choice(units),
            weight=str(round(random.uniform(0.001, 2.0), 3)),
            material=random.choice(materials),
            manufacturer=random.choice(manufacturers),
            lead_time=random.randint(7, 30),
        )
        db.add(p)
        mech_parts.append(p)
    db.flush()

    # 회로자재 600개
    elec_parts = []
    for i in range(1, 601):
        n = offset + i
        p = Part(
            part_number=f'ELEC{n:05d}A',
            description=random.choice(descriptions_elec),
            spec=random.choice(specs_elec),
            category='회로자재',
            unit=random.choice(units),
            weight=str(round(random.uniform(0.0001, 0.5), 4)),
            material=random.choice(materials),
            manufacturer=random.choice(manufacturers),
            lead_time=random.randint(3, 21),
        )
        db.add(p)
        elec_parts.append(p)
    db.flush()

    # 기타자재 580개
    misc_parts = []
    for i in range(1, 581):
        n = offset + i
        p = Part(
            part_number=f'MISC{n:05d}A',
            description=random.choice(descriptions_misc),
            spec='-',
            category='기타',
            unit=random.choice(units),
            weight=str(round(random.uniform(0.001, 1.0), 3)),
            material=random.choice(materials),
            manufacturer=random.choice(manufacturers),
            lead_time=random.randint(1, 14),
        )
        db.add(p)
        misc_parts.append(p)
    db.flush()

    # ── BOM 생성 헬퍼 ──────────────────────────────────────────────────────────

    def create_bom_for_model(model_part, semi_parts, mech_parts, elec_parts, misc_parts, bom_type='E-BOM'):
        # 1. 모델의 BOM Header (직접 자식 = 반제품들)
        model_bom = BOMHeader(
            part_id=model_part.id,
            bom_type=bom_type,
            version="1.0",
            effective_date='2026-01-01',
            status='승인',
        )
        db.add(model_bom)
        db.flush()

        num_l2 = random.randint(3, 5)
        used_semi = random.sample(semi_parts, min(num_l2, len(semi_parts)))
        seq = 0

        for semi in used_semi:
            seq += 10
            db.add(BOMItem(
                bom_id=model_bom.id,
                child_part_id=semi.id,
                quantity=random.randint(1, 3),
                unit='EA',
                seq_no=seq,
            ))
        db.flush()

        # 2. 각 반제품의 자체 BOM Header (직접 자식 = 기구/회로자재)
        for semi in used_semi:
            # 이미 이 반제품에 해당 bom_type의 BOM이 있으면 건너뜀
            existing = db.query(BOMHeader).filter(
                BOMHeader.part_id == semi.id,
                BOMHeader.bom_type == bom_type,
            ).first()
            if existing:
                continue

            semi_bom = BOMHeader(
                part_id=semi.id,
                bom_type=bom_type,
                version="1.0",
                effective_date='2026-01-01',
                status='승인',
            )
            db.add(semi_bom)
            db.flush()

            # Level 3 자재 (반제품의 직접 자식)
            num_l3 = random.randint(5, 10)
            combined = mech_parts + elec_parts
            l3_parts = random.sample(combined, min(num_l3, len(combined)))
            l3_seq = 0
            for p3 in l3_parts:
                l3_seq += 10
                l3_item = BOMItem(
                    bom_id=semi_bom.id,
                    child_part_id=p3.id,
                    quantity=random.choice([1, 1, 2, 2, 3, 4, 5, 10]),
                    unit='EA',
                    seq_no=l3_seq,
                )
                db.add(l3_item)
            db.flush()

            # Level 4: 일부 회로자재가 자체 BOM을 가짐 (30% 확률)
            for p3 in l3_parts:
                if random.random() < 0.3:
                    existing_sub = db.query(BOMHeader).filter(
                        BOMHeader.part_id == p3.id,
                        BOMHeader.bom_type == bom_type,
                    ).first()
                    if existing_sub:
                        continue
                    sub_bom = BOMHeader(
                        part_id=p3.id,
                        bom_type=bom_type,
                        version="1.0",
                        effective_date='2026-01-01',
                        status='승인',
                    )
                    db.add(sub_bom)
                    db.flush()
                    num_l4 = random.randint(2, 5)
                    l4_pool = elec_parts + misc_parts
                    l4_parts = random.sample(l4_pool, min(num_l4, len(l4_pool)))
                    l4_seq = 0
                    for p4 in l4_parts:
                        l4_seq += 10
                        db.add(BOMItem(
                            bom_id=sub_bom.id,
                            child_part_id=p4.id,
                            quantity=random.choice([1, 2, 3, 5, 10, 20]),
                            unit='EA',
                            seq_no=l4_seq,
                        ))
                    db.flush()

            # 대치품 추가 (20%)
            semi_items = db.query(BOMItem).filter(BOMItem.bom_id == semi_bom.id).all()
            sample_size = min(len(semi_items) // 5, 5)
            if sample_size > 0:
                for item in random.sample(semi_items, sample_size):
                    sub_part = random.choice(elec_parts + mech_parts)
                    if sub_part.id != item.child_part_id:
                        db.add(BOMSubstitute(
                            bom_item_id=item.id,
                            substitute_part_id=sub_part.id,
                            priority=1,
                            remark='대치 가능',
                        ))

        db.flush()

    # ── 모델별 BOM 생성 ────────────────────────────────────────────────────────

    for idx, model_part in enumerate(model_parts):
        # 전체 20개: E-BOM
        create_bom_for_model(model_part, semi_parts, mech_parts, elec_parts, misc_parts, bom_type='E-BOM')

        # 10개는 추가로 M-BOM (index 0~9)
        if idx < 10:
            create_bom_for_model(model_part, semi_parts, mech_parts, elec_parts, misc_parts, bom_type='M-BOM')

        # 5개는 추가로 S-BOM (index 0~4)
        if idx < 5:
            create_bom_for_model(model_part, semi_parts, mech_parts, elec_parts, misc_parts, bom_type='S-BOM')

    db.commit()
    return RedirectResponse(url="/bom/parts", status_code=303)
