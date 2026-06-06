from pydantic import BaseModel, Field
from typing import Dict, List


class GeneralEducation(BaseModel):
    class Config:
        extra = "ignore"

    기초교양: int
    균형교양: int
    학문기초: int = 0
    특화교양: int = 0
    대교: int = 0
    교양계: int


class MajorBase(BaseModel):
    class Config:
        extra = "ignore"

    최소전공_필수: int
    최소전공_선택: int


class TrackDetail(BaseModel):
    class Config:
        extra = "ignore"

    심화전공: int
    전공계: int
    자유선택: int


class GraduationRequirement(BaseModel):
    class Config:
        extra = "ignore"

    department: str = Field(..., description="학과명 (예: 컴퓨터공학과)")
    total_credits: int = Field(..., description="졸업 총 학점")
    general_education: GeneralEducation
    major_base: MajorBase
    major_course_codes: List[str] = Field(
        default_factory=list,
        description="성적표상 일반선택 등으로 표시되어도 전공으로 인정할 과목코드 목록",
    )
    tracks: Dict[str, TrackDetail] = Field(
        ...,
        description="'기본전공', '복수전공', '단일부전공' 등을 키(Key)로 가지는 트랙별 학점 정보",
    )
