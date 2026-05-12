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
