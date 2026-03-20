from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional
import math

from app.database import get_db
from app.models import Part

PAGE_SIZE = 20
part_router = APIRouter(prefix="/bom")
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# 1. GET /bom/parts — 부품 목록 (검색 + 페이징)
@part_router.get("/parts")
def list_parts(
    request: Request,
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    page: int = 1,
    frame: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Part)

    if keyword:
        query = query.filter(
            Part.part_number.contains(keyword) | Part.description.contains(keyword)
        )
    if category:
        query = query.filter(Part.category == category)

    total = query.count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages))

    parts = (
        query.order_by(Part.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    return templates.TemplateResponse(
        "bom/part_list.html",
        {
            "request": request,
            "parts": parts,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "search_keyword": keyword or "",
            "search_category": category or "",
            "is_frame": frame,
        },
    )


# 2. GET /bom/parts/new — 부품 등록 폼 (정적 라우트: 동적 라우트보다 먼저 정의)
@part_router.get("/parts/new")
def new_part_form(request: Request, frame: bool = False):
    return templates.TemplateResponse(
        "bom/part_form.html",
        {"request": request, "part": None, "error": None, "is_frame": frame},
    )


# 7. GET /bom/parts/api/search — JSON API (정적 라우트: 동적 라우트보다 먼저 정의)
@part_router.get("/parts/api/search")
def search_parts_api(
    q: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Part)
    if q:
        query = query.filter(
            Part.part_number.contains(q) | Part.description.contains(q)
        )
    parts = query.order_by(Part.part_number).limit(20).all()
    return JSONResponse(
        content=[
            {
                "id": p.id,
                "part_number": p.part_number,
                "description": p.description,
                "spec": p.spec,
                "category": p.category or "",
                "unit": p.unit or "",
            }
            for p in parts
        ]
    )


# 3. POST /bom/parts — 부품 등록 처리
@part_router.post("/parts")
def create_part(
    request: Request,
    part_number: str = Form(...),
    description: str = Form(...),
    spec: str = Form(...),
    category: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    weight: Optional[str] = Form(None),
    material: Optional[str] = Form(None),
    manufacturer: Optional[str] = Form(None),
    lead_time: Optional[int] = Form(None),
    frame: bool = Form(False),
    db: Session = Depends(get_db),
):
    # 중복 part_number 체크
    existing = db.query(Part).filter(Part.part_number == part_number).first()
    if existing:
        return templates.TemplateResponse(
            "bom/part_form.html",
            {
                "request": request,
                "part": None,
                "error": f"부품번호 '{part_number}'는 이미 등록되어 있습니다.",
                "is_frame": frame,
                "form_data": {
                    "part_number": part_number,
                    "description": description,
                    "spec": spec,
                    "category": category or "",
                    "unit": unit or "",
                    "weight": weight or "",
                    "material": material or "",
                    "manufacturer": manufacturer or "",
                    "lead_time": lead_time,
                },
            },
            status_code=422,
        )

    part = Part(
        part_number=part_number,
        description=description,
        spec=spec,
        category=category or None,
        unit=unit or None,
        weight=weight or None,
        material=material or None,
        manufacturer=manufacturer or None,
        lead_time=lead_time,
    )
    db.add(part)
    db.commit()
    db.refresh(part)
    return RedirectResponse(url="/bom/parts", status_code=303)


# 4. GET /bom/parts/{part_id}/edit — 부품 수정 폼
@part_router.get("/parts/{part_id}/edit")
def edit_part_form(
    part_id: int,
    request: Request,
    frame: bool = False,
    db: Session = Depends(get_db),
):
    part = db.query(Part).filter(Part.id == part_id).first()
    if part is None:
        raise HTTPException(status_code=404, detail="부품을 찾을 수 없습니다.")
    return templates.TemplateResponse(
        "bom/part_form.html",
        {"request": request, "part": part, "error": None, "is_frame": frame},
    )


# 5. POST /bom/parts/{part_id}/edit — 부품 수정 처리
@part_router.post("/parts/{part_id}/edit")
def update_part(
    part_id: int,
    request: Request,
    part_number: str = Form(...),
    description: str = Form(...),
    spec: str = Form(...),
    category: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    weight: Optional[str] = Form(None),
    material: Optional[str] = Form(None),
    manufacturer: Optional[str] = Form(None),
    lead_time: Optional[int] = Form(None),
    frame: bool = Form(False),
    db: Session = Depends(get_db),
):
    part = db.query(Part).filter(Part.id == part_id).first()
    if part is None:
        raise HTTPException(status_code=404, detail="부품을 찾을 수 없습니다.")

    # 중복 part_number 체크 (자기 자신 제외)
    existing = (
        db.query(Part)
        .filter(Part.part_number == part_number, Part.id != part_id)
        .first()
    )
    if existing:
        return templates.TemplateResponse(
            "bom/part_form.html",
            {
                "request": request,
                "part": part,
                "error": f"부품번호 '{part_number}'는 이미 등록되어 있습니다.",
                "is_frame": frame,
            },
            status_code=422,
        )

    part.part_number = part_number
    part.description = description
    part.spec = spec
    part.category = category or None
    part.unit = unit or None
    part.weight = weight or None
    part.material = material or None
    part.manufacturer = manufacturer or None
    part.lead_time = lead_time

    db.commit()
    db.refresh(part)
    return RedirectResponse(url="/bom/parts", status_code=303)


# 6. POST /bom/parts/{part_id}/delete — 부품 삭제
@part_router.post("/parts/{part_id}/delete")
def delete_part(
    part_id: int,
    db: Session = Depends(get_db),
):
    part = db.query(Part).filter(Part.id == part_id).first()
    if part is None:
        raise HTTPException(status_code=404, detail="부품을 찾을 수 없습니다.")
    db.delete(part)
    db.commit()
    return RedirectResponse(url="/bom/parts", status_code=303)
