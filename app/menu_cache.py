"""메뉴 데이터 캐시 – 서버 시작 시 DB에서 로드하고 메뉴 변경 시 refresh()."""

_db_factory = None
_cache = {"sections": [], "sidebar": {}, "all_url_map": []}


def init(db_factory):
    global _db_factory
    _db_factory = db_factory
    refresh()


def refresh():
    if not _db_factory:
        return
    from app.models import MenuSection, Screen
    db = _db_factory()
    try:
        # 활성 섹션 (상단 메뉴)
        sections = (
            db.query(MenuSection)
            .filter(MenuSection.is_active == 1)
            .order_by(MenuSection.sort_order, MenuSection.id)
            .all()
        )
        _cache["sections"] = [
            {"code": s.code, "name": s.name, "required_permission": s.required_permission or ""}
            for s in sections
        ]

        # 섹션별 사이드바 아이템
        all_section_codes = [s.code for s in db.query(MenuSection).all()]
        _cache["sidebar"] = {}
        for code in all_section_codes:
            items = (
                db.query(Screen)
                .filter(Screen.section == code, Screen.is_active == 1, Screen.show_in_menu == 1)
                .order_by(Screen.sort_order, Screen.id)
                .all()
            )
            _cache["sidebar"][code] = [
                {"url_pattern": i.url_pattern or "", "name": i.name,
                 "required_permission": i.required_permission or ""}
                for i in items
            ]

        # 전체 URL→섹션 매핑 (updateSidebarByUrl용)
        all_screens = db.query(Screen).filter(Screen.is_active == 1).all()
        _cache["all_url_map"] = [
            {"url": s.url_pattern, "section": s.section}
            for s in all_screens if s.url_pattern
        ]
    finally:
        db.close()


def get_sections():
    return _cache["sections"]


def get_sidebar_items(section_code=None):
    if section_code:
        return _cache["sidebar"].get(section_code, [])
    return _cache["sidebar"]


def get_url_section_map():
    return _cache["all_url_map"]
