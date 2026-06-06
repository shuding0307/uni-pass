import pandas as pd

from app.utils.earned_credit import (
    calculate_earned_credit,
    calculate_earned_credit_from_courses,
    get_department_course_catalog,
    get_major_credit_rules,
    graduation_requirement_to_basic_credits,
)


def test_calculate_earned_credit_prefers_course_catalog_area_type():
    courses_df = pd.DataFrame([
        {"과목코드": "1210001", "교과목명": "글쓰기", "학점": 3, "성적": "A+", "이수구분": "자유선택"},
        {"과목코드": "1330001", "교과목명": "균형과목", "학점": 3, "성적": "B0", "이수구분": "자유선택"},
        {"과목코드": "4840003", "교과목명": "컴퓨터프로그래밍1", "학점": 3, "성적": "P", "이수구분": "일반선택"},
        {"과목코드": "4840028", "교과목명": "컴퓨터그래픽스", "학점": 3, "성적": "F", "이수구분": "전공선택"},
    ])
    course_catalog = {
        "1210001": {"area_type": "기초교양"},
        "1330001": {"area_type": "균형교양"},
        "4840003": {"area_type": "전공필수"},
        "4840028": {"area_type": "전공선택"},
    }

    earned_credit = calculate_earned_credit(courses_df, course_catalog)

    assert earned_credit == {
        "total": 9,
        "basic_general": 3,
        "balanced_general": 3,
        "academic_foundation": 0,
        "major_required": 3,
        "major_elective": 0,
        "advanced_major": 0,
        "free_elective": 0,
    }


def test_calculate_earned_credit_falls_back_to_parsed_area_type_for_unknown_codes():
    courses_df = pd.DataFrame([
        {"과목코드": "9990001", "교과목명": "미등록과목", "학점": 2, "성적": "A0", "이수구분": "학문기초"},
        {"과목코드": "9990002", "교과목명": "미등록자선", "학점": 1, "성적": "NP", "이수구분": "자유선택"},
    ])

    earned_credit = calculate_earned_credit(courses_df, {})

    assert earned_credit["total"] == 2
    assert earned_credit["academic_foundation"] == 2
    assert earned_credit["free_elective"] == 0


def test_major_elective_overflow_moves_to_advanced_major():
    courses_df = pd.DataFrame([
        {"과목코드": f"44710{i:02d}", "교과목명": f"전선{i}", "학점": 3, "성적": "A0", "이수구분": "전공선택"}
        for i in range(12)
    ])
    rules = {"major_required_codes": set(), "major_elective_limit": 27}

    raw_credit = calculate_earned_credit(
        courses_df,
        {},
        major_required_codes=rules["major_required_codes"],
    )
    earned_credit = calculate_earned_credit(
        courses_df,
        {},
        major_required_codes=rules["major_required_codes"],
        major_elective_limit=rules["major_elective_limit"],
        apply_major_cascade=True,
    )

    assert raw_credit["major_elective"] == 36
    assert raw_credit["advanced_major"] == 0
    assert earned_credit["major_elective"] == 27
    assert earned_credit["advanced_major"] == 9
    assert earned_credit["total"] == 36


def test_major_elective_overflow_uses_requirement_limit():
    courses_df = pd.DataFrame([
        {"과목코드": f"44710{i:02d}", "교과목명": f"전선{i}", "학점": 3, "성적": "A0", "이수구분": "전공선택"}
        for i in range(12)
    ])

    earned_credit = calculate_earned_credit(
        courses_df,
        {},
        major_elective_limit=33,
        apply_major_cascade=True,
    )

    assert earned_credit["major_elective"] == 33
    assert earned_credit["advanced_major"] == 3
    assert earned_credit["total"] == 36


def test_course_catalog_major_required_overrides_parsed_area_type_by_course_code():
    courses_df = pd.DataFrame([
        {"과목코드": "4471022", "교과목명": "운영체제", "학점": 3, "성적": "A0", "이수구분": "전공선택"},
        {"과목코드": "4471018", "교과목명": "마이크로프로세서", "학점": 3, "성적": "A0", "이수구분": "전공선택"},
    ])
    rules = get_major_credit_rules("IT대학 컴퓨터공학과")

    earned_credit = calculate_earned_credit(
        courses_df,
        {"4471022": {"area_type": "전공필수"}},
        major_required_codes=rules["major_required_codes"],
        major_elective_limit=rules["major_elective_limit"],
        apply_major_cascade=True,
    )

    assert earned_credit["major_required"] == 3
    assert earned_credit["major_elective"] == 3


def test_computer_science_legacy_catalog_reclassifies_free_electives():
    courses_df = pd.DataFrame([
        {"과목코드": "4471010", "교과목명": "자료구조", "학점": 3, "성적": "B+", "이수구분": "자유선택"},
        {"과목코드": "4471029", "교과목명": "컴퓨터구조", "학점": 3, "성적": "B0", "이수구분": "자유선택"},
        {"과목코드": "4471001", "교과목명": "논리회로", "학점": 3, "성적": "B+", "이수구분": "자유선택"},
        {"과목코드": "4730049", "교과목명": "데이터베이스(강원혁신플랫폼)", "학점": 3, "성적": "A+", "이수구분": "자유선택"},
        {"과목코드": "9002394", "교과목명": "창의적시쓰기", "학점": 1, "성적": "가", "이수구분": "자유선택"},
    ])

    earned_credit = calculate_earned_credit(
        courses_df,
        get_department_course_catalog("IT대학 컴퓨터공학과"),
        major_required_limit=9,
        major_elective_limit=33,
        apply_major_cascade=True,
    )

    assert earned_credit["major_required"] == 6
    assert earned_credit["major_elective"] == 6
    assert earned_credit["free_elective"] == 1


def test_calculate_earned_credit_from_courses_includes_planned_courses():
    courses = [
        {"course_code": "4471010", "name": "자료구조", "credits": 3, "grade": "B+", "area_type": "전공필수"},
        {"course_code": "4471029", "name": "컴퓨터구조", "credits": 3, "grade": "B0", "area_type": "전공필수"},
        *[
            {
                "course_code": f"TAKEN{i}",
                "name": f"기이수전선{i}",
                "credits": 3,
                "grade": "A0",
                "area_type": "전공선택",
            }
            for i in range(11)
        ],
        {"course_code": "48400025", "name": "운영체제", "credits": 3, "area_type": "전공필수"},
        *[
            {
                "course_code": f"PLAN{i}",
                "name": f"시간표전선{i}",
                "credits": 3,
                "area_type": "전공선택",
            }
            for i in range(5)
        ],
    ]

    earned_credit = calculate_earned_credit_from_courses(
        courses,
        major_required_limit=9,
        major_elective_limit=33,
        apply_major_cascade=True,
    )

    assert earned_credit["total"] == 57
    assert earned_credit["major_required"] == 9
    assert earned_credit["major_elective"] == 33
    assert earned_credit["advanced_major"] == 15


def test_graduation_requirement_to_basic_credits_maps_2022_computer_science_shape():
    requirement = {
        "department": "컴퓨터공학과",
        "total_credits": 130,
        "general_education": {
            "기초교양": 17,
            "균형교양": 15,
            "학문기초": 12,
            "교양계": 44,
        },
        "major_base": {
            "최소전공_필수": 9,
            "최소전공_선택": 33,
        },
        "tracks": {
            "기본전공": {
                "심화전공": 27,
                "전공계": 69,
                "자유선택": 17,
            },
        },
    }

    assert graduation_requirement_to_basic_credits(requirement) == {
        "total": 130,
        "basic_general": 17,
        "balanced_general": 15,
        "academic_foundation": 12,
        "specialized_general": 0,
        "university_core": 0,
        "major_required": 9,
        "major_elective": 33,
        "advanced_major": 27,
        "teaching": 0,
        "free_elective": 17,
    }
