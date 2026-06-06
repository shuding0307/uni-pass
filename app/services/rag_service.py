"""PostgreSQL tsvector 기반 RAG 서비스.

pgvector/Elasticsearch 없이 동작. 'simple' 딕셔너리로 공백/문장부호 단위 토큰 분리.
검색 결과는 LLM 프롬프트의 학칙·규정 컨텍스트로 주입된다.

주의: 'simple' tsvector는 한국어 형태소 분석을 하지 않으므로, 시드 텍스트와 검색 키워드를
띄어쓰기로 분리된 동일한 토큰 형태로 맞춰야 매칭된다.
"""

import re
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.rules import GraduationRuleSet


def _keywords_for(deficiency_key: str, department: Optional[str] = None) -> List[str]:
    """deficiency_map 키 → tsvector 검색어 리스트.

    GraduationRuleSet의 기존 키워드 사전을 재사용한다 (신규 하드코딩 방지).
    """
    key = deficiency_key.strip()
    terms: List[str] = []

    # 기초교양_세부영역 형식
    if key.startswith("기초교양_"):
        category = key.replace("기초교양_", "")
        terms.extend(GraduationRuleSet.CATEGORY_SEARCH_KEYWORDS.get(category, [category]))
        terms.append("기초교양")

    # 균형교양_부문 형식
    elif key.startswith("균형교양_"):
        area = key.replace("균형교양_", "")
        terms.extend([area, "균형교양"])

    # 전공 영역
    elif key in ("전공필수", "전공선택", "심화전공"):
        terms.append(key)
        if department:
            terms.append(department[:3])

    # 꿈-설계
    elif key == "필수_꿈설계":
        terms.extend(["꿈-설계", "꿈설계", "진로"])

    # 나머지: 키를 _ 와 공백으로 분리
    else:
        terms.extend(re.split(r"[_\s]+", key))

    return [t for t in terms if t]


class RagService:
    """regulations 테이블을 tsvector로 검색해 관련 규정 스니펫을 반환한다."""

    def __init__(self, db: Session):
        self.db = db

    def search(
        self,
        query_terms: List[str],
        major: Optional[str] = None,
        top_k: int = 3,
    ) -> List[dict]:
        """query_terms와 관련된 규정 스니펫 목록을 반환한다.

        - OR 결합 tsquery (term1 | term2 | ...)
        - major 필터: 해당 학과 + 공통(major IS NULL) 모두 포함
        - ts_headline로 매칭 부분 강조 스니펫 생성
        - 결과 없거나 예외 발생 시 빈 리스트 반환
        """
        if not query_terms:
            return []

        # 작은따옴표·특수문자 제거 후 tsquery 토큰 조합
        safe_terms = [re.sub(r"['\"|&!\\]", "", t).strip() for t in query_terms]
        safe_terms = [t for t in safe_terms if t]
        if not safe_terms:
            return []

        ts_query = " | ".join(f"'{t}'" for t in safe_terms)

        major_filter = ""
        params: dict = {"ts_query": ts_query, "top_k": top_k}
        if major:
            major_filter = "AND (r.major IS NULL OR r.major = :major)"
            params["major"] = major

        # content_vector는 GENERATED 컬럼이라 ORM create_all()에서 생성되지 않으므로
        # 쿼리 시점에 to_tsvector()를 직접 계산한다 (15~100건 규모에서 성능 충분).
        sql = text(f"""
            SELECT
                r.title,
                ts_headline(
                    'simple', r.content,
                    to_tsquery('simple', :ts_query),
                    'MaxWords=60, MinWords=20, MaxFragments=2, StartSel=<<, StopSel=>>'
                ) AS snippet,
                r.source_tag,
                ts_rank(
                    to_tsvector('simple', r.title || ' ' || r.content),
                    to_tsquery('simple', :ts_query)
                ) AS rank
            FROM regulations r
            WHERE r.is_active = TRUE
              AND to_tsvector('simple', r.title || ' ' || r.content)
                  @@ to_tsquery('simple', :ts_query)
              {major_filter}
            ORDER BY rank DESC
            LIMIT :top_k
        """)

        try:
            rows = self.db.execute(sql, params).fetchall()
            return [
                {
                    "title": row.title,
                    "snippet": row.snippet,
                    "source_tag": row.source_tag,
                }
                for row in rows
            ]
        except Exception:
            self.db.rollback()
            return []

    def search_for_deficiencies(
        self,
        deficiency_map: dict,
        department: Optional[str] = None,
        top_k: int = 4,
    ) -> List[dict]:
        """deficiency_map 키 전체에서 검색어를 수집해 통합 검색한다."""
        all_terms: List[str] = []
        for key in deficiency_map:
            all_terms.extend(_keywords_for(key, department))
        # 중복 제거, 순서 유지
        seen: set = set()
        unique = [t for t in all_terms if not (t in seen or seen.add(t))]
        return self.search(unique, major=department, top_k=top_k)

    def build_context(
        self,
        query_terms: List[str],
        major: Optional[str] = None,
        top_k: int = 3,
    ) -> str:
        """LLM 프롬프트에 삽입할 규정 컨텍스트 문자열을 생성한다.

        검색 결과가 없으면 빈 문자열 반환 → 프롬프트에서 규정 섹션 자동 생략.
        """
        results = self.search(query_terms, major=major, top_k=top_k)
        if not results:
            return ""

        lines = ["[관련 학칙·규정]"]
        for r in results:
            tag = f" ({r['source_tag']})" if r.get("source_tag") else ""
            # ts_headline 강조 태그(<<, >>) 제거
            snippet = re.sub(r"<<|>>", "", r["snippet"]).strip()
            lines.append(f"■ {r['title']}{tag}")
            lines.append(f"  {snippet}")
        return "\n".join(lines)

    def build_context_for_deficiencies(
        self,
        deficiency_map: dict,
        department: Optional[str] = None,
    ) -> str:
        """deficiency_map 전체를 대상으로 검색해 컨텍스트 문자열을 반환한다."""
        all_terms: List[str] = []
        for key in deficiency_map:
            all_terms.extend(_keywords_for(key, department))
        seen: set = set()
        unique = [t for t in all_terms if not (t in seen or seen.add(t))]
        return self.build_context(unique, major=department, top_k=4)
