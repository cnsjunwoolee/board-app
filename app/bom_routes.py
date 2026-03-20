from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import Session, joinedload
from typing import Optional
import math
import io

from app.database import get_db
from app.models import Part, BOMHeader, BOMItem, BOMSubstitute

PAGE_SIZE = 20
bom_router = APIRouter(prefix="/bom")
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ── 헬퍼: BOM 트리 빌드 ──────────────────────────────────────────────────────

def build_bom_tree(bom_id: int, db: Session):
    """BOM 아이템을 트리 구조로 빌드 (joinedload로 N+1 방지)"""
    items = (
        db.query(BOMItem)
        .filter(BOMItem.bom_id == bom_id)
        .options(
            joinedload(BOMItem.child_part),
            joinedload(BOMItem.substitutes).joinedload(BOMSubstitute.substitute_part),
        )
        .order_by(BOMItem.seq_no)
        .all()
    )

    root_items = [i for i in items if i.parent_item_id is None]

    def build_node(item, level=1):
        children = sorted(
            [i for i in items if i.parent_item_id == item.id],
            key=lambda x: x.seq_no,
        )
        return {
            "item": item,
            "level": level,
            "children": [build_node(c, level + 1) for c in children],
        }

    return [build_node(i) for i in root_items]


def node_to_dict(node):
    """트리 노드를 JSON 직렬화 가능한 dict로 변환"""
    item = node["item"]
    part = item.child_part
    return {
        "id": item.id,
        "part_number": part.part_number if part else "",
        "description": part.description if part else "",
        "spec": part.spec if part else "",
        "category": part.category or "",
        "quantity": item.quantity,
        "unit": item.unit or "",
        "seq_no": item.seq_no,
        "remark": item.remark or "",
        "level": node["level"],
        "children": [node_to_dict(c) for c in node["children"]],
        "substitutes": [
            {
                "id": s.id,
                "part_number": s.substitute_part.part_number if s.substitute_part else "",
                "description": s.substitute_part.description if s.substitute_part else "",
                "priority": s.priority,
                "remark": s.remark or "",
            }
            for s in item.substitutes
        ],
    }


# ── 1. GET /bom/list ─────────────────────────────────────────────────────────

@bom_router.get("/list")
def bom_list(
    request: Request,
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    frame: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(Part)

    if keyword:
        kw = f"%{keyword}%"
        q = q.filter(
            Part.part_number.ilike(kw) | Part.description.ilike(kw)
        )

    if category:
        q = q.filter(Part.category == category)

    total = q.count()
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(1, min(page, total_pages))

    parts = (
        q.order_by(Part.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )

    # 각 Part에 등록된 BOM 타입 목록 조회
    part_ids = [p.id for p in parts]
    bom_headers = (
        db.query(BOMHeader)
        .filter(BOMHeader.part_id.in_(part_ids))
        .all()
    ) if part_ids else []

    # part_id → {bom_type set}
    bom_type_map: dict[int, set] = {}
    for h in bom_headers:
        bom_type_map.setdefault(h.part_id, set()).add(h.bom_type)

    # 카테고리 목록 (드롭다운용)
    categories = [
        r[0]
        for r in db.query(Part.category).distinct().order_by(Part.category).all()
        if r[0]
    ]

    return templates.TemplateResponse(
        "bom/bom_list.html",
        {
            "request": request,
            "parts": parts,
            "bom_type_map": bom_type_map,
            "keyword": keyword or "",
            "category": category or "",
            "categories": categories,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "is_frame": frame,
            "page_size": PAGE_SIZE,
        },
    )


# ── 2. GET /bom/detail/{part_id} ─────────────────────────────────────────────

@bom_router.get("/detail/{part_id}")
def bom_detail(
    part_id: int,
    request: Request,
    bom_type: str = Query("E-BOM"),
    version: Optional[int] = Query(None),
    effective_date: Optional[str] = Query(None),
    frame: bool = Query(False),
    db: Session = Depends(get_db),
):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="부품을 찾을 수 없습니다.")

    # 해당 part + bom_type의 모든 버전
    all_versions = (
        db.query(BOMHeader)
        .filter(BOMHeader.part_id == part_id, BOMHeader.bom_type == bom_type)
        .order_by(BOMHeader.version.desc())
        .all()
    )

    bom_header = None

    if all_versions:
        if effective_date:
            # effective_date <= 입력일 중 가장 최근
            candidates = [
                h for h in all_versions
                if h.effective_date and h.effective_date <= effective_date
            ]
            if candidates:
                bom_header = max(candidates, key=lambda h: (h.effective_date, h.version))
            else:
                bom_header = all_versions[0]  # fallback: 최신 버전
        elif version is not None:
            bom_header = next((h for h in all_versions if h.version == version), None)
            if not bom_header:
                bom_header = all_versions[0]
        else:
            # 버전 미지정 → 최신 버전
            bom_header = all_versions[0]

    tree = build_bom_tree(bom_header.id, db) if bom_header else []

    # 현재 part에 존재하는 BOM 타입 목록 (탭 표시용)
    existing_bom_types = [
        r[0]
        for r in db.query(BOMHeader.bom_type)
        .filter(BOMHeader.part_id == part_id)
        .distinct()
        .all()
    ]

    return templates.TemplateResponse(
        "bom/bom_detail.html",
        {
            "request": request,
            "part": part,
            "bom_header": bom_header,
            "tree": tree,
            "all_versions": all_versions,
            "bom_type": bom_type,
            "selected_version": bom_header.version if bom_header else None,
            "effective_date": effective_date or "",
            "existing_bom_types": existing_bom_types,
            "is_frame": frame,
        },
    )


# ── 3. GET /bom/api/tree/{bom_id} ─────────────────────────────────────────────

@bom_router.get("/api/tree/{bom_id}")
def api_bom_tree(bom_id: int, db: Session = Depends(get_db)):
    bom_header = db.query(BOMHeader).filter(BOMHeader.id == bom_id).first()
    if not bom_header:
        raise HTTPException(status_code=404, detail="BOM을 찾을 수 없습니다.")

    tree = build_bom_tree(bom_id, db)
    return JSONResponse(content=[node_to_dict(n) for n in tree])


# ── 헬퍼: 트리를 flat 리스트로 변환 (편집용) ────────────────────────────────

def node_to_flat(node, flat_list, parent_idx):
    """트리 노드를 편집용 flat dict로 변환하여 flat_list에 추가"""
    item = node["item"]
    part = item.child_part
    idx = len(flat_list)
    entry = {
        "id": item.id,
        "child_part_id": item.child_part_id,
        "part_number": part.part_number if part else "",
        "description": part.description if part else "",
        "spec": part.spec if part else "",
        "category": part.category or "" if part else "",
        "unit": item.unit or "EA",
        "quantity": item.quantity,
        "seq_no": item.seq_no,
        "remark": item.remark or "",
        "level": node["level"],
        "parent_idx": parent_idx,
        "substitutes": [
            {
                "part_id": s.substitute_part_id,
                "part_number": s.substitute_part.part_number if s.substitute_part else "",
                "description": s.substitute_part.description if s.substitute_part else "",
                "priority": s.priority,
                "remark": s.remark or "",
            }
            for s in item.substitutes
        ],
    }
    flat_list.append(entry)
    for child in node["children"]:
        node_to_flat(child, flat_list, idx)


# ── 4. GET /bom/edit/{part_id} ────────────────────────────────────────────────

@bom_router.get("/edit/{part_id}")
def bom_edit(
    part_id: int,
    request: Request,
    bom_type: str = Query("E-BOM"),
    version: Optional[int] = Query(None),
    frame: bool = Query(False),
    db: Session = Depends(get_db),
):
    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        raise HTTPException(status_code=404, detail="부품을 찾을 수 없습니다.")

    # 해당 part + bom_type의 BOM 조회
    q = db.query(BOMHeader).filter(
        BOMHeader.part_id == part_id,
        BOMHeader.bom_type == bom_type,
    )
    if version is not None:
        bom_header = q.filter(BOMHeader.version == version).first()
    else:
        bom_header = q.order_by(BOMHeader.version.desc()).first()

    # BOM이 없으면 새로 생성
    if not bom_header:
        bom_header = BOMHeader(
            part_id=part_id,
            bom_type=bom_type,
            version=1,
            status="작성중",
        )
        db.add(bom_header)
        db.commit()
        db.refresh(bom_header)

    tree = build_bom_tree(bom_header.id, db)
    flat_list = []
    for node in tree:
        node_to_flat(node, flat_list, None)

    import json
    tree_data_json = json.dumps(flat_list, ensure_ascii=False)

    return templates.TemplateResponse(
        "bom/bom_edit.html",
        {
            "request": request,
            "part": part,
            "bom": bom_header,
            "bom_type": bom_type,
            "tree_data_json": tree_data_json,
            "is_frame": frame,
        },
    )


# ── 5. POST /bom/edit/{part_id}/save ─────────────────────────────────────────

@bom_router.post("/edit/{part_id}/save")
async def bom_save(part_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    bom_type = body.get("bom_type", "E-BOM")
    version = body.get("version", 1)
    effective_date = body.get("effective_date") or None
    status = body.get("status", "작성중")
    items_data = body.get("items", [])

    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return JSONResponse(status_code=404, content={"error": "부품을 찾을 수 없습니다."})

    # BOMHeader 조회 또는 생성
    bom_header = db.query(BOMHeader).filter(
        BOMHeader.part_id == part_id,
        BOMHeader.bom_type == bom_type,
        BOMHeader.version == version,
    ).first()

    if not bom_header:
        bom_header = BOMHeader(
            part_id=part_id,
            bom_type=bom_type,
            version=version,
            effective_date=effective_date,
            status=status,
        )
        db.add(bom_header)
        db.flush()
    else:
        bom_header.effective_date = effective_date
        bom_header.status = status

    # 기존 아이템 전체 삭제 (cascade로 substitutes도 삭제됨)
    db.query(BOMItem).filter(BOMItem.bom_id == bom_header.id).delete(synchronize_session=False)
    db.flush()

    # 새 아이템 생성 (idx 기반으로 parent_item_id 매핑)
    # items_data: [{child_part_id, parent_idx, quantity, unit, seq_no, remark, substitutes: [...]}]
    created_items = {}  # idx → BOMItem

    for idx, item_data in enumerate(items_data):
        child_part_id = item_data.get("child_part_id")
        if not child_part_id:
            continue

        parent_idx = item_data.get("parent_idx")
        parent_item_id = None
        if parent_idx is not None and parent_idx in created_items:
            parent_item_id = created_items[parent_idx].id

        new_item = BOMItem(
            bom_id=bom_header.id,
            parent_item_id=parent_item_id,
            child_part_id=child_part_id,
            quantity=float(item_data.get("quantity", 1)),
            unit=item_data.get("unit", "EA") or "EA",
            seq_no=int(item_data.get("seq_no", idx)),
            remark=item_data.get("remark", "") or "",
        )
        db.add(new_item)
        db.flush()
        created_items[idx] = new_item

        # 대치품 생성
        for sub_data in item_data.get("substitutes", []):
            sub_part_id = sub_data.get("part_id")
            if not sub_part_id:
                continue
            sub = BOMSubstitute(
                bom_item_id=new_item.id,
                substitute_part_id=sub_part_id,
                priority=int(sub_data.get("priority", 1)),
                remark=sub_data.get("remark", "") or "",
            )
            db.add(sub)

    db.commit()
    return JSONResponse(content={"ok": True, "bom_id": bom_header.id, "version": bom_header.version})


# ── 6. POST /bom/edit/{part_id}/upload-excel ─────────────────────────────────

@bom_router.post("/edit/{part_id}/upload-excel")
async def bom_upload_excel(part_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    from openpyxl import load_workbook

    if not file.filename or not file.filename.endswith(".xlsx"):
        return JSONResponse(status_code=400, content={"error": ".xlsx 파일만 업로드 가능합니다."})

    contents = await file.read()
    try:
        wb = load_workbook(io.BytesIO(contents), read_only=True, data_only=True)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"파일 파싱 실패: {str(e)}"})

    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        return JSONResponse(content={"success": 0, "fail": 0, "errors": [], "items": []})

    # 헤더 행 파악 (Level, 부품번호, 수량, 단위, 비고)
    header_row = [str(c).strip() if c else "" for c in rows[0]]
    col_map = {}
    for i, h in enumerate(header_row):
        hl = h.lower()
        if "level" in hl or "lv" in hl or "레벨" in hl:
            col_map["level"] = i
        elif "부품번호" in hl or "part" in hl or "partno" in hl:
            col_map["part_number"] = i
        elif "수량" in hl or "qty" in hl or "quantity" in hl:
            col_map["quantity"] = i
        elif "단위" in hl or "unit" in hl:
            col_map["unit"] = i
        elif "비고" in hl or "remark" in hl:
            col_map["remark"] = i

    # 기본 컬럼 순서 fallback: Level | 부품번호 | 수량 | 단위 | 비고
    if "level" not in col_map:
        col_map["level"] = 0
    if "part_number" not in col_map:
        col_map["part_number"] = 1
    if "quantity" not in col_map:
        col_map["quantity"] = 2
    if "unit" not in col_map:
        col_map["unit"] = 3
    if "remark" not in col_map:
        col_map["remark"] = 4

    success_count = 0
    fail_count = 0
    errors = []
    items = []

    data_rows = rows[1:]
    level_stack = {}  # level → idx in items

    for row_idx, row in enumerate(data_rows, start=2):
        def get_cell(key):
            ci = col_map.get(key)
            if ci is None or ci >= len(row):
                return None
            return row[ci]

        raw_level = get_cell("level")
        raw_pn = get_cell("part_number")

        if not raw_pn:
            continue

        part_number = str(raw_pn).strip()
        if not part_number:
            continue

        try:
            level = int(float(str(raw_level).strip())) if raw_level else 1
        except Exception:
            level = 1

        try:
            qty = float(str(get_cell("quantity")).strip()) if get_cell("quantity") else 1.0
        except Exception:
            qty = 1.0

        unit = str(get_cell("unit")).strip() if get_cell("unit") else "EA"
        remark = str(get_cell("remark")).strip() if get_cell("remark") else ""

        # 부품 조회
        part_obj = db.query(Part).filter(Part.part_number == part_number).first()
        if not part_obj:
            fail_count += 1
            errors.append(f"행 {row_idx}: 부품번호 '{part_number}' 없음")
            continue

        # parent_idx 계산
        parent_idx = None
        if level > 1:
            parent_level = level - 1
            parent_idx = level_stack.get(parent_level)

        current_idx = len(items)
        level_stack[level] = current_idx
        # 현재 레벨보다 깊은 스택 항목 제거
        for lv in list(level_stack.keys()):
            if lv >= level + 1:
                del level_stack[lv]

        items.append({
            "child_part_id": part_obj.id,
            "part_number": part_obj.part_number,
            "description": part_obj.description,
            "spec": part_obj.spec or "",
            "category": part_obj.category or "",
            "unit": unit or part_obj.unit or "EA",
            "quantity": qty,
            "seq_no": current_idx,
            "remark": remark,
            "level": level,
            "parent_idx": parent_idx,
            "substitutes": [],
        })
        success_count += 1

    return JSONResponse(content={
        "success": success_count,
        "fail": fail_count,
        "errors": errors,
        "items": items,
    })


# ── 7. GET /bom/api/part-info/{part_number} ───────────────────────────────────

@bom_router.get("/api/part-info/{part_number:path}")
def api_part_info(part_number: str, db: Session = Depends(get_db)):
    part = db.query(Part).filter(Part.part_number == part_number).first()
    if not part:
        return JSONResponse(content={"found": False})
    return JSONResponse(content={
        "found": True,
        "id": part.id,
        "part_number": part.part_number,
        "description": part.description,
        "spec": part.spec or "",
        "category": part.category or "",
        "unit": part.unit or "EA",
    })


# ── 8. POST /bom/edit/{part_id}/new-version ──────────────────────────────────

@bom_router.post("/edit/{part_id}/new-version")
async def bom_new_version(part_id: int, request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    bom_type = body.get("bom_type", "E-BOM")
    current_version = body.get("version", 1)

    part = db.query(Part).filter(Part.id == part_id).first()
    if not part:
        return JSONResponse(status_code=404, content={"error": "부품을 찾을 수 없습니다."})

    # 원본 BOMHeader 조회
    source_bom = db.query(BOMHeader).filter(
        BOMHeader.part_id == part_id,
        BOMHeader.bom_type == bom_type,
        BOMHeader.version == current_version,
    ).first()
    if not source_bom:
        return JSONResponse(status_code=404, content={"error": "원본 BOM을 찾을 수 없습니다."})

    # 최신 버전 번호 조회
    latest = db.query(BOMHeader).filter(
        BOMHeader.part_id == part_id,
        BOMHeader.bom_type == bom_type,
    ).order_by(BOMHeader.version.desc()).first()
    new_version_no = (latest.version + 1) if latest else 1

    # 새 BOMHeader 생성
    new_bom = BOMHeader(
        part_id=part_id,
        bom_type=bom_type,
        version=new_version_no,
        effective_date=source_bom.effective_date,
        status="작성중",
    )
    db.add(new_bom)
    db.flush()

    # 기존 아이템 트리를 복사 (parent 관계 유지)
    source_items = (
        db.query(BOMItem)
        .filter(BOMItem.bom_id == source_bom.id)
        .options(joinedload(BOMItem.substitutes))
        .order_by(BOMItem.seq_no)
        .all()
    )

    old_to_new_id = {}  # 구 item.id → 새 item.id

    def copy_item(old_item, new_parent_id):
        new_item = BOMItem(
            bom_id=new_bom.id,
            parent_item_id=new_parent_id,
            child_part_id=old_item.child_part_id,
            quantity=old_item.quantity,
            unit=old_item.unit,
            seq_no=old_item.seq_no,
            remark=old_item.remark,
        )
        db.add(new_item)
        db.flush()
        old_to_new_id[old_item.id] = new_item.id

        for sub in old_item.substitutes:
            new_sub = BOMSubstitute(
                bom_item_id=new_item.id,
                substitute_part_id=sub.substitute_part_id,
                priority=sub.priority,
                remark=sub.remark,
            )
            db.add(new_sub)

        children = [i for i in source_items if i.parent_item_id == old_item.id]
        for child in sorted(children, key=lambda x: x.seq_no):
            copy_item(child, new_item.id)

    root_items = [i for i in source_items if i.parent_item_id is None]
    for root in sorted(root_items, key=lambda x: x.seq_no):
        copy_item(root, None)

    db.commit()
    return JSONResponse(content={"ok": True, "version": new_version_no})
