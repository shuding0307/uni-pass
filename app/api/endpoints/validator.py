from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.transcript import ParsedTranscriptResponse, StudentTranscript, PlannedCourse, TakenCourse
from app.models.graduation import GraduationRequirement
from app.services.validator import GraduationValidator
from app.services.recommender import RecommenderService
from app.services.timetable_parser import TimetableParser
from app.utils.transcript_parsing import extract_transcript_tokens
from typing import Dict, Any, List
import shutil
import os
import tempfile

# 도메인 주도 설계(DDD)를 위해 라우터 태그와 경로를 직관적으로 변경합니다.
router = APIRouter(
    tags=["Academic Agent APIs (Parsers & Evaluator)"]
)

@router.post("/api/graduation/evaluate")
async def evaluate_graduation(
    transcript: StudentTranscript,
    requirement: GraduationRequirement,
    db: Session = Depends(get_db)
):
    """
    [졸업 사정 및 시뮬레이션 통합 엔진]
    기이수 성적표(taken_courses)와 계획 시간표(planned_courses)를 모두 포함한 가상 성적표를 분석하여
    최종 졸업 가능 여부, 남은 학점 상세 분석, 학습 부하 경고, 그리고 부족 영역에 대한 맞춤형 과목 추천을 한 번에 제공합니다.
    """
    try:
        # 1. 졸업 사정 및 시뮬레이션 분석 (Validator)
        validator = GraduationValidator(requirement, transcript)
        analysis_result = validator.analyze()
        
        # 2. 분석 결과의 deficiency_map을 기반으로 실시간 과목 추천 (Recommender)
        recommender = RecommenderService(db)
        recommendations = recommender.recommend_courses(
            analysis_result["deficiency_map"], 
            department=requirement.department
        )
        
        return {
            "analysis": analysis_result,
            "recommendations": recommendations
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"평가 중 오류 발생: {str(e)}")

@router.post("/api/timetable/parse", response_model=List[PlannedCourse])
async def parse_timetable(
    file: UploadFile = File(...),
    department: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    [시간표 PDF 전용 파서]
    사용자가 업로드한 K-Cloud 또는 에브리타임 시간표 PDF 파일에서 과목 코드, 명칭, 학점, 건물 정보를 추출합니다.
    학과명(department)을 함께 전달하면 전공 과목을 더 정확하게 식별합니다.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        parser = TimetableParser(db)
        matched_courses = parser.parse_pdf(tmp_path, department)
        os.unlink(tmp_path)
        
        return [
            PlannedCourse(
                course_code=c["course_code"],
                name=c["name"],
                credits=c["credits"],
                area_type=c["area_type"],
                building_name=c.get("building_name")
            ) for c in matched_courses
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시간표 분석 중 오류 발생: {str(e)}")

@router.post("/api/transcript/parse", response_model=ParsedTranscriptResponse)
async def parse_transcript(file: UploadFile = File(...)) -> ParsedTranscriptResponse:
    """
    [성적표 PDF 전용 파서]
    성적표 PDF 파일로부터 학번, 소속 학과, 기본 이수 요건 표 및 전체 기이수 과목 내역을 추출합니다.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        student_info, basic_credits, courses_df = extract_transcript_tokens(tmp_path)

        taken_courses = []
        for _, row in courses_df.iterrows():
            taken_courses.append(
                TakenCourse(
                    course_code=str(row["과목코드"]),
                    name=str(row["교과목명"]),
                    credits=int(row["학점"]),
                    grade=str(row["성적"]),
                    area_type=str(row.get("이수구분", "미분류")),
                )
            )

        student_id = student_info.get("학번")
        total_earned_credits = student_info.get("총취득학점")

        return ParsedTranscriptResponse(
            student_id=student_id,
            department=student_info.get("소속"),
            admission_year=int(student_id[:4]) if student_id else None,
            total_earned_credits=int(total_earned_credits) if total_earned_credits else None,
            basic_credits=basic_credits,
            taken_courses=taken_courses,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성적표 분석 중 오류 발생: {str(e)}")
    finally:
        await file.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
