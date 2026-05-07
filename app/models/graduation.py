from pydantic import BaseModel, Field
from typing import Dict

class GeneralEducation(BaseModel):
    기초교양: int
    균형교양: int
    학문기초: int
    교양계: int

class MajorBase(BaseModel):
    최소전공_필수: int
    최소전공_선택: int

class TrackDetail(BaseModel):
    심화전공: int
    전공계: int
    자유선택: int

class GraduationRequirement(BaseModel):
    department: str = Field(..., description="학과명 (예: 컴퓨터공학과)")
    total_credits: int = Field(..., description="졸업 총 학점")
    general_education: GeneralEducation
    major_base: MajorBase
    tracks: Dict[str, TrackDetail] = Field(
        ..., 
        description="'기본전공', '복수전공', '단일부전공' 등을 키(Key)로 가지는 트랙별 학점 정보"
    )