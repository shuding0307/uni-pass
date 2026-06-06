import pdfplumber
import re
import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.models.db import Course
from typing import List, Dict


@dataclass
class CatalogCourse:
    course_code: str
    name: str
    credits: int
    area_type: str
    sub_area: str | None = None
    building_name: str | None = None


def _parse_credits(raw: str | None) -> int:
    if not raw:
        return 0
    first = str(raw).split("-")[0].strip()
    try:
        return int(first)
    except ValueError:
        return 0


@lru_cache(maxsize=1)
def _load_fallback_courses() -> List[CatalogCourse]:
    base_dir = Path(__file__).resolve().parents[2]
    csv_path = base_dir / "data" / "parsed_schedule.csv"
    if not csv_path.exists():
        return []

    courses_by_code: dict[str, CatalogCourse] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            code = (row.get("과목코드") or "").strip()
            name = (row.get("과목명") or "").strip()
            if not code or not name or code in courses_by_code:
                continue
            courses_by_code[code] = CatalogCourse(
                course_code=code,
                name=name.replace("\n", " "),
                credits=_parse_credits(row.get("시수")),
                area_type=(row.get("구분") or "미분류").strip() or "미분류",
                sub_area=(row.get("부문") or "").strip() or None,
                building_name=(row.get("건물") or "").strip() or None,
            )
    return list(courses_by_code.values())


class TimetableParser:
    def __init__(self, db: Session | None = None):
        self.db = db

    def parse_pdf(self, pdf_path: str, department: str = None) -> List[Dict]:
        """K-Cloud 시간표 PDF에서 표 구조를 인식하여 과목을 추출합니다."""
        matched_courses = []
        seen_codes = set()
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # 1. 표 데이터 추출 (리스트의 리스트 형태)
                table = page.extract_table()
                
                if table:
                    # 표가 발견되면 각 칸(Cell) 단위로 텍스트를 정제하여 매칭
                    for row in table:
                        for cell in row:
                            if not cell: continue
                            # 한 칸 내에서 줄바꿈을 공백으로 바꾸고 매칭 시도
                            cleaned_cell = cell.replace('\n', ' ')
                            found = self._match_in_text(cleaned_cell, department)
                            for c in found:
                                if c["course_code"] not in seen_codes:
                                    matched_courses.append(c)
                                    seen_codes.add(c["course_code"])
                else:
                    # 표 인식이 안 되는 경우를 대비한 폴백 (기존 좌표 정렬 방식)
                    words = page.extract_words()
                    sorted_words = sorted(words, key=lambda w: (round(w['top'] / 2) * 2, w['x0']))
                    fallback_text = " ".join([w['text'] for w in sorted_words])
                    found = self._match_in_text(fallback_text, department)
                    for c in found:
                        if c["course_code"] not in seen_codes:
                            matched_courses.append(c)
                            seen_codes.add(c["course_code"])
                            
        return matched_courses

    def _match_in_text(self, text: str, department: str = None) -> List[Dict]:
        """주어진 텍스트 블록에서 DB 과목과 건물 정보를 정확하게 찾아냅니다."""
        # 1. 건물명 추출 (예: 한빛관, 공6호관, 60주년기념관)
        building_pattern = re.compile(r'([가-힣0-9]+(?:관|호관))')
        building_match = building_pattern.search(text)
        building_name = building_match.group(1) if building_match else None

        # 2. 공백 제거 버전으로 과목 매칭
        def sanitize(t):
            return re.sub(r'\s+', '', t)
        
        cleaned_source = sanitize(text)
        if len(cleaned_source) < 2: return []
        
        all_courses = self._get_courses()
        sorted_courses = sorted(all_courses, key=lambda x: len(sanitize(x.name)), reverse=True)
        
        matched_in_block = []
        temp_source = cleaned_source
        
        for course in sorted_courses:
            target_name = sanitize(course.name)
            if len(target_name) < 2: continue
            
            if target_name in temp_source:
                is_better = True
                for existing in matched_in_block:
                    if sanitize(existing['name']) == target_name:
                        better = self._pick_better_course(
                            Course(course_code=existing['course_code'], area_type=existing['area_type'], sub_area=existing['sub_area']), 
                            course, 
                            department
                        )
                        if better.course_code == course.course_code:
                            matched_in_block.remove(existing)
                        else:
                            is_better = False
                        break
                
                if is_better:
                    matched_in_block.append({
                        "course_code": course.course_code,
                        "name": course.name,
                        "credits": course.credits,
                        "area_type": course.area_type,
                        "sub_area": course.sub_area,
                        "building_name": building_name # 추출된 건물명 추가
                    })
                    temp_source = temp_source.replace(target_name, "[OK]")
                    
        return matched_in_block

    def _pick_better_course(self, c1: Course, c2: Course, department: str) -> Course:
        """두 과목 중 사용자 상황에 더 적합한 과목을 반환합니다."""
        # 1. 교양/자유선택 우선
        def is_ge(c): return "교양" in c.area_type or "자유선택" in c.area_type
        if is_ge(c1) and not is_ge(c2): return c1
        if is_ge(c2) and not is_ge(c1): return c2
        
        # 2. 학과 일치 여부 우선
        if department:
            dept_keyword = department[:3]
            def matches_dept(c): return c.sub_area and dept_keyword in c.sub_area
            if matches_dept(c1) and not matches_dept(c2): return c1
            if matches_dept(c2) and not matches_dept(c1): return c2
            
        return c1

    def _get_courses(self) -> List[Course | CatalogCourse]:
        if self.db is not None:
            try:
                courses = self.db.query(Course).all()
                if courses:
                    return courses
            except SQLAlchemyError:
                pass

        return _load_fallback_courses()
