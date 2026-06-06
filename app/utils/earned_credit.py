from typing import Any, Dict, Iterable, Mapping, Optional

import pandas as pd

EARNED_CREDIT_KEYS = [
    "total",
    "basic_general",
    "balanced_general",
    "academic_foundation",
    "major_required",
    "major_elective",
    "advanced_major",
    "free_elective",
]

FAIL_GRADES = {"F", "NP", "U", "FA"}

COMPUTER_SCIENCE_MAJOR_ELECTIVE_LIMIT = 27

COMPUTER_SCIENCE_LEGACY_COURSE_AREAS = {
    "4471022": "전공필수",  # 운영체제
    "4471029": "전공필수",  # 컴퓨터구조
    "4471010": "전공필수",  # 자료구조
    "4471001": "전공선택",  # 논리회로
    "4471012": "전공선택",  # 선형대수학
    "4471013": "전공선택",  # 리눅스프로그래밍
    "4471016": "전공선택",  # 알고리즘
    "4471017": "전공선택",  # 데이터분석프로그래밍
    "4471018": "전공선택",  # 마이크로프로세서
    "4471019": "전공선택",  # 문제해결프로그래밍
    "4471023": "전공선택",  # 데이터통신
    "4471025": "전공선택",  # 신호처리
    "4471026": "전공선택",  # 컴퓨터그래픽스
    "4471028": "전공선택",  # 프로그래밍언어
    "4471030": "전공선택",  # 데이터베이스
    "4471031": "전공선택",  # 디지털영상처리
    "4471034": "전공선택",  # 컴퓨터네트워크
    "4471047": "전공선택",  # 네트워크보안
    "4471049": "전공선택",  # 실전코딩
    "4471056": "전공선택",  # 고급파이썬프로그래밍
    "4471057": "전공선택",  # 인공지능수학
    "4471059": "전공선택",  # 취업·창업과꿈-설계
    "4730038": "전공선택",  # 선형대수학(강원혁신플랫폼)
    "4730049": "전공선택",  # 데이터베이스(강원혁신플랫폼)
}

AREA_BUCKET_ALIASES = {
    "기초": "basic_general",
    "기교": "basic_general",
    "교약": "basic_general",
    "교필": "basic_general",
    "기초교양": "basic_general",
    "균형": "balanced_general",
    "균교": "balanced_general",
    "균형교양": "balanced_general",
    "학문": "academic_foundation",
    "학문기초": "academic_foundation",
    "전필": "major_required",
    "전공필수": "major_required",
    "전선": "major_elective",
    "전공선택": "major_elective",
    "심화": "advanced_major",
    "심전": "advanced_major",
    "심화전공": "advanced_major",
    "자선": "free_elective",
    "자유선택": "free_elective",
    "일선": "free_elective",
    "일반선택": "free_elective",
}


def empty_earned_credit() -> Dict[str, int]:
    return {key: 0 for key in EARNED_CREDIT_KEYS}


def normalize_area_to_earned_bucket(area_type: Optional[str]) -> Optional[str]:
    if not area_type:
        return None

    normalized = str(area_type).replace(" ", "").strip()
    if normalized in AREA_BUCKET_ALIASES:
        return AREA_BUCKET_ALIASES[normalized]

    for alias, bucket in AREA_BUCKET_ALIASES.items():
        if alias in normalized:
            return bucket

    return None


def calculate_earned_credit(
    courses_df: pd.DataFrame,
    course_catalog: Mapping[str, Any],
    major_required_codes: Optional[set[str]] = None,
    major_required_limit: Optional[int] = None,
    major_elective_limit: Optional[int] = None,
    apply_major_cascade: bool = False,
) -> Dict[str, int]:
    earned_credit = empty_earned_credit()
    major_required_codes = major_required_codes or set()

    if courses_df.empty:
        return earned_credit

    for _, row in courses_df.iterrows():
        grade = str(row.get("성적", "")).strip().upper()
        if grade in FAIL_GRADES:
            continue

        try:
            credits = int(float(row.get("학점", 0)))
        except (TypeError, ValueError):
            continue

        course_code = str(row.get("과목코드", "")).strip()
        matched_course = course_catalog.get(course_code)
        matched_area = getattr(matched_course, "area_type", None)

        if matched_area is None and isinstance(matched_course, Mapping):
            matched_area = matched_course.get("area_type")

        area_type = matched_area or row.get("이수구분")
        bucket = normalize_area_to_earned_bucket(area_type)
        if course_code in major_required_codes:
            bucket = "major_required"

        earned_credit["total"] += credits
        if bucket:
            earned_credit[bucket] += credits

    if (
        apply_major_cascade
        and major_required_limit is not None
        and earned_credit["major_required"] > major_required_limit
    ):
        overflow = earned_credit["major_required"] - major_required_limit
        earned_credit["major_required"] = major_required_limit
        earned_credit["major_elective"] += overflow

    if (
        apply_major_cascade
        and major_elective_limit is not None
        and earned_credit["major_elective"] > major_elective_limit
    ):
        overflow = earned_credit["major_elective"] - major_elective_limit
        earned_credit["major_elective"] = major_elective_limit
        earned_credit["advanced_major"] += overflow

    return earned_credit


def build_course_catalog(courses: Iterable[Any]) -> Dict[str, Any]:
    return {
        str(getattr(course, "course_code", "")).strip(): course
        for course in courses
        if getattr(course, "course_code", None)
    }


def get_department_course_catalog(department: Optional[str]) -> Dict[str, Dict[str, str]]:
    normalized_department = (department or "").replace(" ", "").lower()
    if "컴퓨터공학" in normalized_department:
        return {
            course_code: {"area_type": area_type}
            for course_code, area_type in COMPUTER_SCIENCE_LEGACY_COURSE_AREAS.items()
        }

    return {}


def get_major_credit_rules(department: Optional[str]) -> Dict[str, Any]:
    normalized_department = (department or "").replace(" ", "").lower()
    if "컴퓨터공학" in normalized_department:
        return {
            "major_required_codes": set(),
            "major_required_limit": None,
            "major_elective_limit": COMPUTER_SCIENCE_MAJOR_ELECTIVE_LIMIT,
        }

    return {
        "major_required_codes": set(),
        "major_required_limit": None,
        "major_elective_limit": None,
    }


def graduation_requirement_to_basic_credits(requirement: Optional[Mapping[str, Any]]) -> Dict[str, int]:
    basic_credits = {
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

    if not requirement:
        return basic_credits

    general_education = requirement.get("general_education", {})
    major_base = requirement.get("major_base", {})
    primary_track = requirement.get("tracks", {}).get("기본전공", {})

    basic_credits["total"] = int(requirement.get("total_credits") or 0)
    basic_credits["basic_general"] = int(general_education.get("기초교양") or 0)
    basic_credits["balanced_general"] = int(general_education.get("균형교양") or 0)
    basic_credits["academic_foundation"] = int(general_education.get("학문기초") or 0)
    basic_credits["major_required"] = int(major_base.get("최소전공_필수") or 0)
    basic_credits["major_elective"] = int(major_base.get("최소전공_선택") or 0)
    basic_credits["advanced_major"] = int(primary_track.get("심화전공") or 0)
    basic_credits["free_elective"] = int(primary_track.get("자유선택") or 0)
    return basic_credits
