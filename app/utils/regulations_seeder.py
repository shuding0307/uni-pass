"""regulations 테이블 시드 스크립트.

두 가지 소스:
  1. data/regulations_seed.json — 큐레이션된 학칙 산문 (주 데이터)
  2. data/raw_requirements/*.pdf — 학과별 이수학점 한 줄 산문 (보조 데이터)

idempotent: (title, source_tag) 중복이면 skip.
content_vector는 DB GENERATED ALWAYS 컬럼이라 insert 시 포함하지 않는다.
embedding(VECTOR) 컬럼은 pgvector 미설치이므로 건드리지 않는다.
"""

import glob
import json
import os
from datetime import date

from app.core.database import SessionLocal
from app.models.db import Regulation
from app.services.parser import RequirementParser


def _already_exists(db, title: str, source_tag: str) -> bool:
    return (
        db.query(Regulation)
        .filter(Regulation.title == title, Regulation.source_tag == source_tag)
        .first()
        is not None
    )


def seed_from_json(db, json_path: str) -> int:
    """JSON 파일에서 학칙 산문을 읽어 insert. 삽입된 건수 반환."""
    with open(json_path, encoding="utf-8") as f:
        items = json.load(f)

    count = 0
    for item in items:
        title = item["title"]
        source_tag = item.get("source_tag", "학칙")
        if _already_exists(db, title, source_tag):
            continue
        reg = Regulation(
            title=title,
            content=item["content"],
            major=item.get("major"),
            source_tag=source_tag,
            effective_date=date.fromisoformat(item["effective_date"]),
            is_active=True,
        )
        db.add(reg)
        count += 1

    db.commit()
    return count


def seed_from_pdfs(db, pdf_dir: str) -> int:
    """졸업요건 PDF에서 학과별 이수학점을 한 줄 산문으로 변환해 insert. 삽입된 건수 반환."""
    parser = RequirementParser()
    # 모든 학과 목록을 대표 PDF에서 추출
    pdfs = sorted(glob.glob(os.path.join(pdf_dir, "*.pdf")))

    # 학과명 목록 — 파서가 지원하는 대표 학과들
    target_depts = [
        "컴퓨터공학과", "전자공학과", "소프트웨어학과", "수학과", "물리학과",
        "경영학과", "경제학과", "국어국문학과", "영어영문학과",
    ]

    count = 0
    for pdf_path in pdfs:
        year_tag = os.path.basename(pdf_path).replace("이수학점표_", "").replace("학년도.pdf", "")
        try:
            admission_year = int(year_tag)
        except ValueError:
            continue

        for dept in target_depts:
            try:
                result = parser.parse(pdf_path, target_dept=dept)
            except Exception:
                continue
            if not result:
                continue

            ge = result.get("general_education", {})
            mb = result.get("major_base", {})
            total = result.get("total_credits", 130)
            tracks = result.get("tracks", {})
            primary = tracks.get("기본전공", {})

            content = (
                f"{admission_year}학번 {dept} 졸업요건: "
                f"기초교양 {ge.get('기초교양', 0)}학점, "
                f"균형교양 {ge.get('균형교양', 0)}학점, "
                f"교양계 {ge.get('교양계', 0)}학점, "
                f"전공필수 {mb.get('최소전공_필수', 0)}학점, "
                f"전공선택 {mb.get('최소전공_선택', 0)}학점, "
                f"심화전공 {primary.get('심화전공', 0)}학점, "
                f"자유선택 {primary.get('자유선택', 0)}학점, "
                f"총 {total}학점 이수 시 졸업 가능."
            )
            title = f"{admission_year}학번 {dept} 졸업 이수요건"
            source_tag = f"이수학점표_{year_tag}"

            if _already_exists(db, title, source_tag):
                continue

            reg = Regulation(
                title=title,
                content=content,
                major=dept,
                source_tag=source_tag,
                effective_date=date(admission_year, 3, 1),
                is_active=True,
            )
            db.add(reg)
            count += 1

    db.commit()
    return count


def run():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    json_path = os.path.join(base_dir, "data", "regulations_seed.json")
    pdf_dir = os.path.join(base_dir, "data", "raw_requirements")

    db = SessionLocal()
    try:
        print("=== regulations 시드 시작 ===")
        n1 = seed_from_json(db, json_path)
        print(f"  학칙 산문 JSON: {n1}건 삽입")
        n2 = seed_from_pdfs(db, pdf_dir)
        print(f"  졸업요건 PDF 보조 시드: {n2}건 삽입")
        total = n1 + n2
        print(f"  합계: {total}건 삽입 (중복 skip 포함)")
        print(f"  현재 테이블 총 행 수: {db.query(Regulation).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
