from pydantic import BaseModel, Field
from typing import List, Optional

class TakenCourse(BaseModel):
    course_code: str = Field(..., description="과목코드 (예: 4111001)")
    name: str = Field(..., description="과목명")
    credits: int = Field(..., description="학점수")
    area_type: str = Field(..., description="성적표 상의 이수구분 (예: 전필, 기초교양)")
    grade: str = Field(..., description="성적 (예: A+, F)")
    sub_area: Optional[str] = Field(default=None, description="균형교양 세부 부문 (예: 자연과기술)")
    
class StudentTranscript(BaseModel):
    student_id: str
    admission_year: int = Field(..., description="입학년도 (2019 이상이어야 함)")
    taken_courses: List[TakenCourse]