# RAG 구현 계획 — PostgreSQL tsvector + 큐레이션된 학칙 산문

> 이 문서는 구현 담당 모델을 위한 작업 지시서입니다. 대화 맥락 없이 이 문서만으로 구현 가능하도록 작성했습니다.

## 0. 현재 상태 (전제)
- FastAPI 백엔드(`uni-pass`). 졸업 사정 + AI 시간표 추천 기능이 이미 구현·동작 중.
- 엔드포인트 `POST /api/timetable/recommend` 존재. 내부에서 `GraduationValidator`로 `deficiency_map`
  (부족 영역→부족 학점)을 구하고 `TimetableRecommenderService`가 시간 충돌 없는 후보 시간표를
  만든 뒤 **LLM이 후보 중 2~3개를 골라 추천 사유를 생성**한다 (하이브리드).
- LLM 래퍼: `app/services/llm_client.py` (`LLMClient.complete_json(system, user)`, 키 없으면 폴백).
- `regulations` 테이블: 스키마/모델 존재하나 **데이터 0건**, 검색 로직 없음.
- **pgvector는 DB에 미설치** (벡터 검색 불가). **`to_tsvector('simple', ...)` 한국어 검색은 동작 확인됨.**
- DB 접속: `app/core/database.py::SessionLocal`. 실행은 `.venv/Scripts/python.exe`, `$env:PYTHONPATH="."`.

## 1. 목표
현재 LLM은 **후보 시간표 JSON만** 받아 추천 사유를 만든다. 학칙 근거가 없어 맥락이 약하다.
부족 영역/상황 키워드로 **실제 학칙 산문**을 tsvector 검색해 LLM 프롬프트에 주입,
"재수강은 직전 성적 C+ 이하만 가능…", "한 학기 최대 18학점…" 같은 **규정 근거가 담긴 추천 사유**를 만든다.

**핵심 설계 결정**: RAG 데이터 소스는 이수학점표 PDF(숫자 표)가 아니라 **큐레이션한 학칙 산문**이다.
PDF 숫자만으로는 `deficiency_map`이 이미 가진 값을 되풀이할 뿐이라 RAG 가치가 없다.

---

## 2. 구현 항목

### (1) 큐레이션 학칙 데이터 — `data/regulations_seed.json` (신규)
실제 강원대 학칙/수강 규정을 본뜬 **산문 형태** JSON 배열. 각 항목:
```json
{ "title": "...", "content": "...", "major": null,
  "source_tag": "학칙-수강", "effective_date": "2023-03-01" }
```
- `major`: 특정 학과 규정이면 학과명, 전체 공통이면 `null`.
- 수록 범위(추천에 실제로 쓰이는 규정 위주, 10~15건):
  수강 학점 제한(학기당 최소/최대, 성적우수자 추가), 재수강 규정(대상 성적·인정 학점·성적표기),
  전공 이수(전공필수/선택 최소학점, 복수·부전공), 교양 이수(글로벌의사소통/디지털리터러시 필수,
  균형교양 4부문), 계절학기, F/NP 처리, 졸업 유예 등.
- ⚠️ **tsvector 매칭 주의**: `'simple'` 딕셔너리는 형태소 분석 없이 공백/문장부호로만 토큰 분리
  (부분 매칭 안 됨). content에 검색 키워드(글로벌의사소통, 디지털리터러시, 재수강, 전공필수 등)가
  **띄어쓰기로 분리된 토큰**으로 등장하도록 작성할 것.
- ⚠️ 큐레이션 텍스트는 일반 대학 학칙 패턴 기반 초안 → 실제 공식 학칙으로 대조·교체 권장(시드라 교체 쉬움).

### (2) 시더 — `app/utils/regulations_seeder.py` (신규)
- `data/regulations_seed.json`을 읽어 `regulations`에 insert (주 데이터).
- (보조) `data/raw_requirements/*.pdf`의 학과별 이수학점을 한 줄 산문으로 변환해 추가 시드.
  예: `"2023학번 컴퓨터공학과 졸업요건: 기초교양 17학점, 균형교양 15학점, 전공필수 9학점, 총 130학점."`
  → `app/services/parser.py::RequirementParser.parse(path, target_dept=...)` 재사용.
- **중복 방지**: `(title, source_tag)` 이미 있으면 skip (idempotent).
- `content_vector`는 DB가 GENERATED ALWAYS로 자동 생성하므로 insert 시 넣지 말 것.
- `embedding`(VECTOR) 컬럼은 pgvector 없으므로 건드리지 말 것 (NULL 유지).
- 실행: `$env:PYTHONPATH="."; .venv/Scripts/python.exe app/utils/regulations_seeder.py`

### (3) RAG 서비스 — `app/services/rag_service.py` (신규)
```
class RagService:
    def __init__(self, db: Session)
    def search(self, query_terms: list[str], major: str|None=None, top_k: int=3) -> list[dict]
    def build_context(self, query_terms: list[str], major: str|None=None) -> str
```
- `search`: `to_tsquery('simple', 'term1 | term2 | ...')` OR 결합. major 필터는
  `(major IS NULL OR major = :major)` (해당 학과 + 공통 모두). `ts_rank` 내림차순 top_k.
  `ts_headline('simple', content, query, 'MaxWords=60,MinWords=20,MaxFragments=2')`로 스니펫.
  검색어에서 작은따옴표 등 위험 문자 제거. 예외 시 빈 리스트.
- `build_context`: 검색 결과를 `"[관련 학칙·규정]\n■ {title}\n  {snippet}" ...` 문자열로.
  **결과 없으면 빈 문자열** 반환(→ 프롬프트에서 규정 섹션 생략, RAG 없이도 동작 보장).
- raw SQL은 `sqlalchemy.text()` + 바인드 파라미터 사용.

### (4) 키워드 생성 — 기존 룰셋 재사용 (신규 하드코딩 금지)
`deficiency_map` 키 → 검색어 변환은 **`app/services/rules.py`의 `GraduationRuleSet`** 를 재사용한다
(`CATEGORY_SEARCH_KEYWORDS`, `basic_ge_rules()`에 이미 키워드 사전 있음).
- `기초교양_글로벌의사소통` → 접두어 제거 후 `CATEGORY_SEARCH_KEYWORDS["글로벌의사소통"]` + `["기초교양"]`
- `균형교양_인간과문화` → `["인간과문화", "균형교양"]`
- `전공필수`/`전공선택` → `[키, department[:3]]`
- 나머지 → 키를 `_`/공백으로 분리
작은 헬퍼 `_keywords_for(key, department)`로 구현 (RagService 또는 추천기 안).

### (5) 추천기 통합 — `app/services/timetable_recommender.py` 수정
- `__init__`에 `self.rag = RagService(db)` 추가.
- `_llm_user_prompt(...)`: `deficiency_map` 키들 + `department`로 키워드 모아
  `self.rag.build_context(terms, major=department)` 호출 → user 프롬프트 JSON에
  `"regulations_context"` 필드로 추가(빈 문자열이면 필드 생략).
- `_llm_system_prompt()`: "제공된 학칙·규정 내용을 근거로 추천 사유를 작성하라" 문장 추가.
- LLM 미사용(폴백) 경로는 변경하지 말 것 (RAG는 LLM 경로에만 영향).

### (6) 규정 관리 API — `app/schemas/regulation.py` + `app/api/endpoints/regulations.py` (신규)
- `POST /api/regulations` — 등록 (title, content, major?, source_tag?, effective_date).
- `GET /api/regulations` — 목록 조회 (major 필터 옵션).
- `app/main.py`에 `include_router` 등록 (기존 graduation/validator 라우터와 동일 패턴).

---

## 3. 재사용 자산 (새로 만들지 말 것)
- `regulations` 테이블 + `content_vector`(tsvector, 자동생성): `db/schema.sql:153`, `app/models/db.py:99`
- 키워드 사전: `GraduationRuleSet.CATEGORY_SEARCH_KEYWORDS`, `basic_ge_rules()` — `app/services/rules.py`
- 졸업요건 PDF 파서: `RequirementParser.parse()` — `app/services/parser.py`
- LLM 래퍼: `app/services/llm_client.py` (변경 없음)
- 주입 지점: `TimetableRecommenderService._llm_user_prompt()` / `_llm_system_prompt()`
  — `app/services/timetable_recommender.py`

---

## 4. 검증 방법
1. **시드 확인**:
   `$env:PYTHONPATH="."; .venv/Scripts/python.exe -c "from app.core.database import SessionLocal; from app.models.db import Regulation; db=SessionLocal(); print('규정 수:', db.query(Regulation).count())"`
2. **RAG 검색 단독**:
   `$env:PYTHONPATH="."; .venv/Scripts/python.exe -c "from app.core.database import SessionLocal; from app.services.rag_service import RagService; print(RagService(SessionLocal()).build_context(['글로벌의사소통','재수강'], major='컴퓨터공학과'))"`
3. **추천 API 규정 근거 반영**: 서버(`uvicorn app.main:app`) 실행 후 `POST /api/timetable/recommend`
   호출 → `rationale`에 학칙 근거 문구 포함 확인. (LLM 키 없으면 폴백으로 정상 응답되는지도 확인)
4. **pytest**: `$env:PYTHONPATH="."; .venv/Scripts/python.exe -m pytest -q` — 기존 33개 회귀 없음
   + RAG 단위 테스트(`tests/test_rag_service.py`, DB는 MagicMock 또는 통합 스킵 마커) 추가.

## 5. 주의사항
- DB 트랜잭션: raw SQL 실행 중 오류 나면 세션이 aborted 되니 예외 처리 시 rollback 고려.
- `'simple'` tsvector는 한국어 형태소 분석을 하지 않는다 — 합성어/조사 결합어는 매칭 안 됨.
  시드 텍스트와 검색 키워드를 띄어쓰기 토큰으로 맞춰야 한다.
- pgvector/임베딩은 이번 범위 밖. `embedding` 컬럼은 NULL 유지.
