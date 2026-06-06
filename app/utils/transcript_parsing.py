import re

import pandas as pd
import pdfplumber

from app.services.base_parser import BasePdfParser


AREA_MAP = {
    "기초": "기초교양",
    "기교": "기초교양",
    "교약": "기초교양",
    "교필": "기초교양",
    "균형": "균형교양",
    "균교": "균형교양",
    "특화": "특화교양",
    "특교": "특화교양",
    "대교": "대교",
    "전필": "전공필수",
    "전선": "전공선택",
    "심화": "심화전공",
    "심전": "심화전공",
    "자선": "자유선택",
    "일선": "일반선택",
    "교직": "교직",
    "학문": "학문기초",
}

AREA_PATTERN = "|".join(sorted(map(re.escape, AREA_MAP), key=len, reverse=True))

BASIC_CREDIT_DEFAULTS = {
    "total": 0,
    "basic_general": 0,
    "balanced_general": 0,
    "academic_foundation": 0,
    "specialized_general": 0,
    "university_core": 0,
    "major_required": 0,
    "major_elective": 0,
    "advanced_major": 0,
    "teaching": 0,
    "free_elective": 0,
}


class TranscriptParser(BasePdfParser):
    """성적표 PDF에서 학생 정보, 기본이수학점, 과목 내역을 추출합니다."""

    def parse(self, path: str, **kwargs):
        return extract_transcript_tokens(path)


def _empty_student_info():
    return {
        "학번": None,
        "이름": None,
        "소속": None,
        "department": None,
        "총취득학점": None,
    }


def _parse_basic_credits(nums):
    basic_credits = BASIC_CREDIT_DEFAULTS.copy()
    values = []
    for num in nums:
        try:
            values.append(int(float(num)))
        except (TypeError, ValueError):
            values.append(0)

    if not values:
        return basic_credits

    if len(values) >= 9 and values[-1] >= 100:
        keys = [
            "basic_general",
            "balanced_general",
            "specialized_general",
            "university_core",
            "major_required",
            "major_elective",
            "advanced_major",
            "free_elective",
        ]
        basic_credits["total"] = values[-1]
        for key, value in zip(keys, values[:-1]):
            basic_credits[key] = value
        return basic_credits

    keys = [
        "basic_general",
        "balanced_general",
        "specialized_general",
        "university_core",
        "major_required",
        "major_elective",
        "advanced_major",
        "teaching",
        "free_elective",
        "total",
    ]
    for key, value in zip(keys, values):
        basic_credits[key] = value
    return basic_credits


def _parse_transcript_text(text):
    student_info = _empty_student_info()
    basic_credits = BASIC_CREDIT_DEFAULTS.copy()
    courses = []

    if not text.strip():
        return student_info, basic_credits, pd.DataFrame(courses)

    student_match = re.search(
        r"(\d{9})\s+([가-힣]{2,4})\s+[남여]\w*\s+[\d\.]+\s+"
        r"([^\n]*?(?:대학|학부)\s+[^\n]*?(?:학과|학부|전공))",
        text,
    )
    if student_match:
        department = student_match.group(3).strip()
        student_info["학번"] = student_match.group(1)
        student_info["이름"] = student_match.group(2)
        student_info["소속"] = department
        student_info["department"] = department
    else:
        id_match = re.search(r"20\d{7}", text)
        if id_match:
            student_info["학번"] = id_match.group(0)

        if student_info["학번"]:
            name_match = re.search(rf'{student_info["학번"]}\s+([가-힣]{{2,4}})', text)
            if name_match:
                student_info["이름"] = name_match.group(1)

        dept_match = re.search(r"[^\n]*?(?:대학|학부)\s+[^\n]*?(?:학과|학부|전공)", text)
        if dept_match:
            department = dept_match.group(0).strip()
            student_info["소속"] = department
            student_info["department"] = department

    earned_match = re.search(r"(?:총취득학점|취득학점\s*합계)\s*[:\s]*(\d+(?:\.\d)?)", text)
    if earned_match:
        try:
            student_info["총취득학점"] = int(float(earned_match.group(1)))
        except (ValueError, TypeError):
            pass

    basic_match = re.search(r"기본이수학점\s+([\d\s]+)", text)
    if basic_match:
        basic_credits = _parse_basic_credits(basic_match.group(1).split())

    seen_codes = set()
    course_pattern = re.compile(
        rf"(?<!\S)({AREA_PATTERN})\s+"
        r"(\d{7})\s+"
        r"(.+?)\s+"
        r"(?:(?:원격|재수강|원|재|MD|M|D|R|N)\s+)*"
        r"(\d+(?:\.\d)?)\s+"
        r"([A-D][+0]|F|P|NP|가|부)\s+"
        r"(\d{4}[\.-](?:[12]|[a-dA-D]))",
        re.MULTILINE,
    )

    for line in text.split("\n"):
        for match in course_pattern.finditer(line):
            try:
                area_code = match.group(1)
                code = match.group(2)
                name = re.sub(r"\s+", " ", match.group(3)).strip()
                credits_val = int(float(match.group(4)))
                grade = match.group(5)

                if len(name) > 40:
                    continue

                if code not in seen_codes:
                    courses.append(
                        {
                            "과목코드": code,
                            "교과목명": name,
                            "학점": credits_val,
                            "성적": grade,
                            "이수구분": AREA_MAP.get(area_code, area_code),
                            "이수구분원문": area_code,
                        }
                    )
                    seen_codes.add(code)
            except (ValueError, TypeError, IndexError):
                continue

    courses_df = pd.DataFrame(courses)
    if not student_info["총취득학점"] and not courses_df.empty:
        student_info["총취득학점"] = int(courses_df["학점"].sum())

    return student_info, basic_credits, courses_df


def extract_transcript_tokens(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        return _parse_transcript_text(text)
    except Exception:
        return _empty_student_info(), BASIC_CREDIT_DEFAULTS.copy(), pd.DataFrame([])
