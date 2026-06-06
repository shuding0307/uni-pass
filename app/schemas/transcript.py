from pydantic import BaseModel
from typing import List, Optional, Dict

from app.models.transcript import TakenCourse


class ParsedTranscriptResponse(BaseModel):
    student_name: Optional[str] = None
    student_id: Optional[str] = None
    department: Optional[str] = None
    admission_year: Optional[int] = None
    total_earned_credits: Optional[int] = None
    basic_credits: Dict[str, str] = {}
    taken_courses: List[TakenCourse] = []
