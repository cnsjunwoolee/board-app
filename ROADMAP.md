# 게시판 웹앱 ROADMAP

## 현재 작업 (2026-03-17)
모드: 자동진행

- [x] 1. 프로젝트 환경 설정 (impl-sonnet)
- [x] 2. DB 모델 & 초기화 (impl-sonnet) [blockedBy: 1]
- [x] 3. FastAPI 라우터 & 비즈니스 로직 (impl-sonnet) [blockedBy: 2]
- [x] 4. HTML 템플릿 & CSS 스타일링 (impl-sonnet) [blockedBy: 3]

진행률: 4/4 (100%)

## BOM 관리 시스템 (2026-03-20)
모드: 자동진행
- [x] 1. BOM 모델 정의 + DB 마이그레이션 + 메뉴 권한 (impl-sonnet)
- [x] 2. 부품 CRUD 라우트 + 템플릿 (impl-sonnet) [blockedBy: 1]
- [x] 3. BOM 조회/상세 라우트 + Tree Table (impl-sonnet) [blockedBy: 1]
- [x] 4. BOM 편집 모드 - Tree Editor + DnD + Excel + 검색 (impl-sonnet) [blockedBy: 3]
- [x] 5. 메뉴/사이드바 통합 + main.py 라우터 등록 (impl-sonnet) [blockedBy: 1]
- [x] 6. 시드 데이터 생성 - 2000부품 + 4~5 Level BOM (impl-sonnet) [blockedBy: 1, 3]
진행률: 6/6 (100%)

## 기술 스택
- FastAPI (Python 웹 프레임워크)
- SQLite + SQLAlchemy (데이터베이스)
- Jinja2 (서버사이드 HTML 템플릿)
- Bootstrap (CSS 스타일링)
- uvicorn (ASGI 서버)
