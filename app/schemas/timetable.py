from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from app.models.transcript import StudentTranscript
from app.models.graduation import GraduationRequirement


class TimetableRecommendRequest(BaseModel):
    """시간표 추천 요청. 졸업 사정에 필요한 성적표/요건과 추천 옵션을 함께 받는다."""

    transcript: StudentTranscript
    requirement: GraduationRequirement
    semester: str = Field("2026-1", description="추천 대상 학기 (CourseOffering.semester)")
    target_credits_min: int = Field(15, description="목표 학점 하한")
    target_credits_max: int = Field(18, description="목표 학점 상한")
    prefer_no_early: bool = Field(False, description="1교시(이른 아침) 수업 회피 선호")
    optimize_walking: bool = Field(False, description="연속 수업 간 건물 이동 거리 최소화 선호")
    num_alternatives: int = Field(3, ge=1, le=5, description="추천 시간표 대안 개수")


class RecommendedCourse(BaseModel):
    course_code: str
    name: str
    credits: int
    area_type: str
    section: Optional[str] = None
    professor: Optional[str] = None
    schedule: Optional[str] = None
    building_name: Optional[str] = None


class RecommendedTimetable(BaseModel):
    courses: List[RecommendedCourse]
    total_credits: int
    covered_deficiencies: List[str] = Field(
        default_factory=list, description="이 시간표가 채워주는 부족 영역 키 목록"
    )
    rationale: str = Field("", description="추천 사유 (LLM 생성 또는 결정론적 폴백 문구)")


class TimetableRecommendResponse(BaseModel):
    deficiency_map: Dict[str, object] = Field(default_factory=dict)
    timetables: List[RecommendedTimetable] = Field(default_factory=list)
    llm_used: bool = Field(False, description="LLM 선택/사유 생성 사용 여부 (False면 폴백)")
