import pytest
from app.services.validator import GraduationValidator
from app.models.transcript import StudentTranscript, TakenCourse
from app.models.graduation import GraduationRequirement

# 1. 모든 테스트에서 공통으로 사용할 '정답지(졸업요건)' 세팅
@pytest.fixture
def base_requirement():
    return GraduationRequirement(
        major="컴퓨터공학",
        department="컴퓨터공학부",
        admission_year=2023,
        total_credits=130,
        major_base={
            "최소전공_필수": 9,
            "최소전공_선택": 33
        },
        general_education={
            "기초교양": 17,
            "균형교양": 15,
            "학문기초": 0,
            "교양계": 32
        },
        advanced_major=27,
        # 👇 tracks 안의 구조를 Pydantic 모델이 원하는 대로 상세히 작성!
        tracks={
            "기본전공": {
                "심화전공": 27,   # 심화전공 필수 학점
                "전공계": 69,     # 전공 총합 (9 + 33 + 27)
                "자유선택": 29    # 전체(130) - 전공(69) - 교양(32) = 29
            }
        }
    )

# 2. 시나리오: 전공필수 학점 부족 케이스
def test_major_core_deficiency(base_requirement):
    # 전필 6학점만 이수한 데이터
    transcript = StudentTranscript(
        student_id="20230001",
        admission_year=2023,
        taken_courses=[
            TakenCourse(course_code="CS101", name="자료구조", credits=3, area_type="전공필수", grade="A+"),
            TakenCourse(course_code="CS102", name="알고리즘", credits=3, area_type="전공필수", grade="B0")
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    assert result["is_graduatable"] is False
    assert result["deficiency_map"]["전공필수"] == 3  # 9 - 6 = 3학점 부족해야 함

# 3. 시나리오: 폭포수 로직 (전필 -> 전선 이월) 테스트
def test_major_overflow_cascade(base_requirement):
    # 전필 12학점(9학점 초과), 전선 30학점 이수
    transcript = StudentTranscript(
        student_id="20230002",
        admission_year=2023,
        taken_courses=[
            # 전필 12학점
            TakenCourse(course_code="C1", name="과목1", credits=3, area_type="전공필수", grade="P"),
            TakenCourse(course_code="C2", name="과목2", credits=3, area_type="전공필수", grade="P"),
            TakenCourse(course_code="C3", name="과목3", credits=3, area_type="전공필수", grade="P"),
            TakenCourse(course_code="C4", name="과목4", credits=3, area_type="전공필수", grade="P"),
            # 전선 30학점
            TakenCourse(course_code="E1", name="선택1", credits=30, area_type="전공선택", grade="A0")
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    # 전필에서 넘친 3학점이 전선으로 가서 전선 요건(33)을 채워야 함
    assert result["buckets_status"]["전공필수"] == 9
    assert result["buckets_status"]["전공선택"] == 33
    assert "전공선택" not in result["deficiency_map"]

# 4. 시나리오: 마이크로 룰 (꿈-설계) 누락 테스트
def test_dream_design_missing(base_requirement):
    transcript = StudentTranscript(
        student_id="20230003",
        admission_year=2023,
        taken_courses=[
            # 꿈-설계를 1개만 들었을 때
            TakenCourse(course_code="D1", name="진로탐색과 꿈-설계", credits=1, area_type="자유선택", grade="P")
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    assert "필수_꿈설계" in result["deficiency_map"]

# 5. 시나리오: F학점 및 NP 제외 테스트
def test_fail_grade_exclusion(base_requirement):
    transcript = StudentTranscript(
        student_id="20230004",
        admission_year=2023,
        taken_courses=[
            TakenCourse(course_code="F1", name="낙제과목", credits=3, area_type="전공필수", grade="F"),
            TakenCourse(course_code="N1", name="논패스과목", credits=1, area_type="교양", grade="NP")
        ]
    )
    
    validator = GraduationValidator(base_requirement, transcript)
    result = validator.analyze()
    
    assert result["total_valid_credits"] == 0