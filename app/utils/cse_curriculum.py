import re
from functools import lru_cache
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional

import requests

CSE_CURRICULUM_URL = "https://cse.kangwon.ac.kr/cse/curriculum/undergraduate-subject.do"

CURRICULUM_AREA_MAP = {
    "전필": "전공필수",
    "전선": "전공선택",
}


class CurriculumTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: List[List[str]] = []
        self._in_row = False
        self._in_cell = False
        self._current_row: List[str] = []
        self._current_cell: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "tr":
            self._in_row = True
            self._current_row = []
        elif tag == "td" and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._in_cell:
            text = " ".join("".join(self._current_cell).split())
            self._current_row.append(text)
            self._in_cell = False
            self._current_cell = []
        elif tag == "tr" and self._in_row:
            if self._current_row:
                self.rows.append(self._current_row)
            self._in_row = False
            self._current_row = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)


def _clean_course_name(raw_name: str) -> str:
    name = re.split(r"\s*학년/학기\s*:", raw_name, maxsplit=1)[0]
    return name.strip()


def _parse_credit(raw_credit: str) -> int:
    match = re.search(r"\d+", raw_credit)
    return int(match.group()) if match else 0


def parse_cse_curriculum_html(html: str) -> Dict[str, Dict[str, object]]:
    parser = CurriculumTableParser()
    parser.feed(html)

    catalog: Dict[str, Dict[str, object]] = {}
    for row in parser.rows:
        if len(row) < 5:
            continue

        area_type = CURRICULUM_AREA_MAP.get(row[1].strip(), row[1].strip())
        course_code = row[2].strip()
        if not re.fullmatch(r"\d{7,8}", course_code):
            continue

        catalog[course_code] = {
            "area_type": area_type,
            "name": _clean_course_name(row[3]),
            "credits": _parse_credit(row[4]),
        }

    return catalog


@lru_cache(maxsize=8)
def fetch_cse_curriculum_catalog(year: Optional[int]) -> Dict[str, Dict[str, object]]:
    if not year:
        return {}

    response = requests.get(
        CSE_CURRICULUM_URL,
        params={"srSearchKey": str(year)},
        timeout=5,
    )
    response.raise_for_status()
    return parse_cse_curriculum_html(response.text)


def fetch_first_available_cse_curriculum_catalog(years: Iterable[Optional[int]]) -> Dict[str, Dict[str, object]]:
    for year in years:
        try:
            catalog = fetch_cse_curriculum_catalog(year)
        except requests.RequestException:
            continue
        if catalog:
            return catalog

    return {}
