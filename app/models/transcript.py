from pydantic import BaseModel, Field
from typing import List, Optional

class TakenCourse(BaseModel):
    course_code: str = Field(..., description="과목코드 (예: 4111001)")
    name: str = Field(..., description="과목명")
    credits: int = Field(..., description="학점수")
    area_type: str = Field(..., description="성적표 상의 이수구분 (예: 전필, 기초교양)")
    grade: str = Field(..., description="성적 (예: A+, F)")
    sub_area: Optional[str] = Field(default=None, description="균형교양 세부 부문 (예: 자연과기술)")

class PlannedCourse(BaseModel):
    course_code: str = Field(..., description="과목코드")
    name: str = Field(..., description="과목명")
    credits: int = Field(..., description="학점수")
    area_type: str = Field(..., description="이수구분 (예상)")
    building_name: Optional[str] = Field(default=None, description="건물명")

class StudentTranscript(BaseModel):
    student_id: str
    admission_year: int = Field(..., description="입학년도 (2019 이상이어야 함)")
    taken_courses: List[TakenCourse]
    planned_courses: List[PlannedCourse] = Field(default_factory=list, description="현재 수강 중이거나 계획 중인 과목들")

class EarnedCredit(BaseModel):
    total: int = Field(default=0, description="총 이수 학점")
    basic_general: int = Field(default=0, description="교양 기초")
    balanced_general: int = Field(default=0, description="균형 교양")
    academic_foundation: int = Field(default=0, description="학문 기초")
    major_required: int = Field(default=0, description="전공 필수")
    major_elective: int = Field(default=0, description="전공 선택")
    advanced_major: int = Field(default=0, description="심화 전공")
    free_elective: int = Field(default=0, description="자유 선택")

class BasicCredits(BaseModel):
    total: int = Field(default=0, description="기본 이수 총 학점")
    basic_general: int = Field(default=0, description="기초 교양")
    balanced_general: int = Field(default=0, description="균형 교양")
    academic_foundation: int = Field(default=0, description="학문 기초")
    specialized_general: int = Field(default=0, description="특화 교양")
    university_core: int = Field(default=0, description="대학 핵심")
    major_required: int = Field(default=0, description="전공 필수")
    major_elective: int = Field(default=0, description="전공 선택")
    advanced_major: int = Field(default=0, description="심화 전공")
    teaching: int = Field(default=0, description="교직")
    free_elective: int = Field(default=0, description="자유 선택")

class ParsedTranscriptResponse(BaseModel):
    student_id: Optional[str] = Field(default=None, description="성적표에서 추출한 학번")
    student_name: Optional[str] = Field(default=None, description="성적표에서 추출한 이름")
    department: Optional[str] = Field(default=None, description="성적표에서 추출한 학과")
    admission_year: Optional[int] = Field(default=None, description="학번 기준 입학년도")
    total_earned_credits: Optional[int] = Field(default=None, description="총취득학점")
    earned_credit: EarnedCredit = Field(default_factory=EarnedCredit, description="과목코드 매칭 기반 영역별 이수 학점")
    basic_credits: BasicCredits = Field(default_factory=BasicCredits, description="졸업 이수 요건 기준 학점")
    taken_courses: List[TakenCourse] = Field(default_factory=list, description="성적표에서 추출한 기이수 과목")
