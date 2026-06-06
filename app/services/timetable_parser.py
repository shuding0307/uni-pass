import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.db import Course
from app.services.base_parser import BasePdfParser


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


class TimetableParser(BasePdfParser):
    def __init__(self, db: Session | None = None):
        self.db = db

    def parse_pdf(self, pdf_path: str, department: str = None) -> List[Dict]:
        return self.parse(pdf_path, department=department)

    def parse(self, path: str, department: str = None, **kwargs) -> List[Dict]:
        """K-Cloud 시간표 PDF에서 표 구조를 인식하여 과목을 추출합니다."""
        matched_courses = []
        seen_codes = set()

        with self.open_pdf(path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()

                if table:
                    for row in table:
                        for cell in row:
                            if not cell:
                                continue
                            found = self._match_in_text(cell.replace("\n", " "), department)
                            for course in found:
                                if course["course_code"] not in seen_codes:
                                    matched_courses.append(course)
                                    seen_codes.add(course["course_code"])
                else:
                    words = page.extract_words()
                    sorted_words = sorted(words, key=lambda w: (round(w["top"] / 2) * 2, w["x0"]))
                    fallback_text = " ".join(w["text"] for w in sorted_words)
                    found = self._match_in_text(fallback_text, department)
                    for course in found:
                        if course["course_code"] not in seen_codes:
                            matched_courses.append(course)
                            seen_codes.add(course["course_code"])

        return matched_courses

    def _match_in_text(self, text: str, department: str = None) -> List[Dict]:
        """주어진 텍스트 블록에서 DB 과목과 건물 정보를 찾아냅니다."""
        building_pattern = re.compile(r"([가-힣0-9]+(?:관|호관))")
        building_match = building_pattern.search(text)
        building_name = building_match.group(1) if building_match else None

        def sanitize(value):
            return re.sub(r"\s+", "", value)

        cleaned_source = sanitize(text)
        if len(cleaned_source) < 2:
            return []

        all_courses = self._get_courses()
        sorted_courses = sorted(all_courses, key=lambda x: len(sanitize(x.name)), reverse=True)

        matched_in_block = []
        temp_source = cleaned_source

        for course in sorted_courses:
            target_name = sanitize(course.name)
            if len(target_name) < 2:
                continue

            if target_name in temp_source:
                is_better = True
                for existing in matched_in_block:
                    if sanitize(existing["name"]) == target_name:
                        existing_course = CatalogCourse(
                            course_code=existing["course_code"],
                            name=existing["name"],
                            credits=existing["credits"],
                            area_type=existing["area_type"],
                            sub_area=existing["sub_area"],
                            building_name=existing["building_name"],
                        )
                        better = self._pick_better_course(existing_course, course, department)
                        if better.course_code == course.course_code:
                            matched_in_block.remove(existing)
                        else:
                            is_better = False
                        break

                if is_better:
                    matched_in_block.append(
                        {
                            "course_code": course.course_code,
                            "name": course.name,
                            "credits": course.credits,
                            "area_type": course.area_type,
                            "sub_area": course.sub_area,
                            "building_name": building_name,
                        }
                    )
                    temp_source = temp_source.replace(target_name, "[OK]")

        return matched_in_block

    def _pick_better_course(self, c1, c2, department: str):
        """두 과목 중 사용자 상황에 더 적합한 과목을 반환합니다."""
        def is_ge(course):
            return "교양" in course.area_type or "자유선택" in course.area_type

        if is_ge(c1) and not is_ge(c2):
            return c1
        if is_ge(c2) and not is_ge(c1):
            return c2

        if department:
            dept_keyword = department[:3]

            def matches_dept(course):
                return course.sub_area and dept_keyword in course.sub_area

            if matches_dept(c1) and not matches_dept(c2):
                return c1
            if matches_dept(c2) and not matches_dept(c1):
                return c2

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
