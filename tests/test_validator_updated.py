import pytest
from app.services.validator import GraduationValidator
from app.models.transcript import StudentTranscript, TakenCourse
from app.models.graduation import GraduationRequirement

@pytest.fixture
def base_requirement():
    return GraduationRequirement(
        department="컴퓨터공학과",
        total_credits=130,
        major_base={
            "최소전공_필수": 9,
            "최소전공_선택": 33
        },
        major_course_codes=["CS101", "CS102", "CS201"], # 전공 인정 코드
        general_education={
            "기초교양": 17,
            "균형교양": 15,
            "학문기초": 0,
            "교양계": 32
        },
        tracks={
            "기본전공": {
                "심화전공": 27,
                "전공계": 69,
                "자유선택": 29
            }
        }
    )

def test_ge_overflow_to_free_choice_and_evaporation(base_requirement):
    # 기초교양 17학점 기준, 30학점 이수 시나리오
    # 17(기초) + 10(자선) + 3(증발)
    transcript = StudentTranscript(
        student_id="20230001",
        admission_year=2023,
        taken_courses=[
            TakenCourse(course_code=f"GE{i}", name=f"교양{i}", credits=3, area_type="기초교양", grade="A0")
            for i in range(10) # 3 * 10 = 30학점
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    # 기초교양은 딱 17점만 남아야 함
    assert result["buckets_status"]["기초교양"] == 17
    # 초과분 중 10점은 자선으로 가야 함
    assert result["buckets_status"]["자유선택"] == 10
    # 총 유효 학점은 17 + 10 = 27점이어야 함 (3점 증발)
    assert result["total_valid_credits"] == 27

def test_major_recognition_by_code(base_requirement):
    # 성적표에는 '일반선택'으로 찍혀있지만 과목코드가 전공인 경우
    transcript = StudentTranscript(
        student_id="20230002",
        admission_year=2023,
        taken_courses=[
            TakenCourse(course_code="CS101", name="자료구조", credits=3, area_type="일반선택", grade="A+"),
            TakenCourse(course_code="CS102", name="알고리즘", credits=3, area_type="일반선택", grade="B+")
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    # 전공선택 바구니에 6점이 담겨야 함 (일반선택 -> 전공선택 자동 분류)
    assert result["buckets_status"]["전공선택"] == 6
    assert result["buckets_status"]["자유선택"] == 0

def test_ge_overflow_within_limit(base_requirement):
    # 기초교양 17학점 기준, 20학점 이수 (3점 초과)
    # 17(기초) + 3(자선) + 0(증발)
    transcript = StudentTranscript(
        student_id="20230003",
        admission_year=2023,
        taken_courses=[
            TakenCourse(course_code="GE1", name="교양1", credits=10, area_type="기초교양", grade="A0"),
            TakenCourse(course_code="GE2", name="교양2", credits=10, area_type="기초교양", grade="A0")
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    assert result["buckets_status"]["기초교양"] == 17
    assert result["buckets_status"]["자유선택"] == 3
    assert result["total_valid_credits"] == 20

def test_2021_basic_ge_and_balanced_area_rules_are_not_over_applied():
    requirement = GraduationRequirement(
        department="컴퓨터공학과",
        total_credits=130,
        major_base={"최소전공_필수": 0, "최소전공_선택": 0},
        general_education={
            "기초교양": 10,
            "균형교양": 12,
            "특화교양": 1,
            "대교": 18,
            "교양계": 41,
        },
        tracks={"기본전공": {"심화전공": 0, "전공계": 0, "자유선택": 89}},
    )
    transcript = StudentTranscript(
        student_id="20210001",
        admission_year=2021,
        taken_courses=[
            TakenCourse(course_code="1100005", name="글쓰기와말하기(자연공학)", credits=3, area_type="기초교양", grade="A+"),
            TakenCourse(course_code="1100008", name="의사소통영어(듣기,말하기)", credits=2, area_type="기초교양", grade="A0"),
            TakenCourse(course_code="1100009", name="의사소통영어(읽기,쓰기)", credits=2, area_type="기초교양", grade="A0"),
            TakenCourse(course_code="1100007", name="컴퓨팅사고력(공학)", credits=3, area_type="기초교양", grade="A0"),
            TakenCourse(course_code="1210001", name="균형1", credits=3, area_type="균형교양", grade="A0"),
            TakenCourse(course_code="1220001", name="균형2", credits=3, area_type="균형교양", grade="A0"),
            TakenCourse(course_code="1230001", name="균형3", credits=3, area_type="균형교양", grade="A0"),
            TakenCourse(course_code="1240001", name="균형4", credits=3, area_type="균형교양", grade="A0"),
            TakenCourse(course_code="1300001", name="특화", credits=1, area_type="특화교양", grade="A0"),
            TakenCourse(course_code="1400001", name="대교1", credits=18, area_type="자유선택", grade="A0"),
            TakenCourse(course_code="4144991", name="진로탐색과 꿈-설계", credits=1, area_type="자유선택", grade="P"),
            TakenCourse(course_code="4471059", name="취업·창업과 꿈-설계", credits=1, area_type="전공선택", grade="P"),
        ],
    )

    result = GraduationValidator(requirement, transcript).analyze()

    assert result["buckets_status"]["대교"] == 18
    assert "기초교양_글로벌의사소통" not in result["deficiency_map"]
    assert "기초교양_디지털리터러시" not in result["deficiency_map"]
    assert not any(key.startswith("균형교양_") for key in result["deficiency_map"])

def test_2022_balanced_area_rules_are_applied(base_requirement):
    transcript = StudentTranscript(
        student_id="20220001",
        admission_year=2022,
        taken_courses=[
            TakenCourse(course_code="1210001", name="문학의이해", credits=3, area_type="균형교양", grade="A0", sub_area="인간과문화"),
            TakenCourse(course_code="1220001", name="사회의이해", credits=3, area_type="균형교양", grade="A0", sub_area="사회와세계"),
            TakenCourse(course_code="1230001", name="과학의이해", credits=3, area_type="균형교양", grade="A0", sub_area="자연과기술"),
        ],
    )

    result = GraduationValidator(base_requirement, transcript).analyze()

    assert result["deficiency_map"]["균형교양_예술과건강"] == 1
