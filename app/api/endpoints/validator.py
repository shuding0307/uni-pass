from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.transcript import StudentTranscript, PlannedCourse
from app.models.graduation import GraduationRequirement
from app.services.validator import GraduationValidator
from app.services.recommender import RecommenderService
from app.services.report_service import ReportService
from app.services.timetable_parser import TimetableParser
from app.services.timetable_recommender import TimetableRecommenderService
from app.schemas.timetable import (
    TimetableRecommendRequest,
    TimetableRecommendResponse,
    RecommendedTimetable,
    RecommendedCourse,
)
from app.utils.transcript_parsing import extract_transcript_tokens
from typing import Dict, Any, List
import shutil
import os
import tempfile

router = APIRouter(tags=["Academic Agent APIs (Parsers & Evaluator)"])


@router.post("/api/graduation/evaluate")
async def evaluate_graduation(
    transcript: StudentTranscript,
    requirement: GraduationRequirement,
    db: Session = Depends(get_db),
):
    """
    [졸업 사정 및 시뮬레이션 통합 엔진]
    기이수 성적표(taken_courses)와 계획 시간표(planned_courses)를 모두 포함한 가상 성적표를 분석하여
    졸업 가능 여부, 남은 학점 분석, 학습 부하 경고, 맞춤형 과목 추천을 한 번에 제공합니다.
    분석 결과는 DB에 영속화됩니다.
    """
    try:
        validator = GraduationValidator(requirement, transcript)
        analysis_result = validator.analyze()

        recommender = RecommenderService(db)
        recommendations = recommender.recommend_courses(
            analysis_result["deficiency_map"],
            department=requirement.department,
        )

        # 결과 영속화 (DB 오류 시 graceful degradation — 분석 결과는 그대로 반환)
        ReportService(db).save_result(
            student_id=transcript.student_id,
            admission_year=transcript.admission_year,
            requirement=requirement,
            analysis=analysis_result,
        )

        return {"analysis": analysis_result, "recommendations": recommendations}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"평가 중 오류 발생: {str(e)}")


@router.get("/api/students/{student_id}/history")
async def get_analysis_history(
    student_id: str,
    db: Session = Depends(get_db),
):
    """
    [졸업 사정 이력 조회]
    특정 학번의 과거 졸업 사정 결과를 최신순으로 반환합니다.
    """
    history = ReportService(db).get_history(student_id)
    return {"student_id": student_id, "history": history}


@router.post("/api/timetable/parse", response_model=List[PlannedCourse])
async def parse_timetable(
    file: UploadFile = File(...),
    department: str = Form(None),
    db: Session = Depends(get_db),
):
    """
    [시간표 PDF 전용 파서]
    K-Cloud 또는 에브리타임 시간표 PDF에서 과목 코드, 명칭, 학점, 건물 정보를 추출합니다.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        matched_courses = TimetableParser(db).parse(tmp_path, department=department)
        os.unlink(tmp_path)

        return [
            PlannedCourse(
                course_code=c["course_code"],
                name=c["name"],
                credits=c["credits"],
                area_type=c["area_type"],
                building_name=c.get("building_name"),
            )
            for c in matched_courses
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시간표 분석 중 오류 발생: {str(e)}")


@router.post("/api/timetable/recommend", response_model=TimetableRecommendResponse)
async def recommend_timetable(
    req: TimetableRecommendRequest,
    db: Session = Depends(get_db),
):
    """
    [AI 기반 시간표 추천]
    성적표/졸업요건으로 부족 영역을 산출한 뒤, 시간 충돌이 없고 목표 학점에 맞는
    추천 시간표 2~3안을 생성합니다. 코드가 하드 제약(충돌·학점·후보)을 보장하고,
    LLM은 그 안에서 선택/순위와 추천 사유를 담당합니다(키 없거나 실패 시 결정론적 폴백).
    """
    try:
        validator = GraduationValidator(req.requirement, req.transcript)
        analysis = validator.analyze()
        deficiency_map = analysis["deficiency_map"]

        taken_codes = {c.course_code for c in req.transcript.taken_courses}

        service = TimetableRecommenderService(db)
        timetables, llm_used = service.recommend(
            deficiency_map=deficiency_map,
            department=req.requirement.department,
            semester=req.semester,
            taken_codes=taken_codes,
            target_min=req.target_credits_min,
            target_max=req.target_credits_max,
            prefer_no_early=req.prefer_no_early,
            optimize_walking=req.optimize_walking,
            num_alternatives=req.num_alternatives,
        )

        return TimetableRecommendResponse(
            deficiency_map=deficiency_map,
            llm_used=llm_used,
            timetables=[
                RecommendedTimetable(
                    total_credits=t.total_credits,
                    covered_deficiencies=t.covered_deficiencies,
                    rationale=t.rationale,
                    courses=[
                        RecommendedCourse(
                            course_code=o.course_code,
                            name=o.name,
                            credits=o.credits,
                            area_type=o.area_type,
                            section=o.section,
                            professor=o.professor,
                            schedule=o.schedule,
                            building_name=o.building_name,
                        )
                        for o in t.offerings
                    ],
                )
                for t in timetables
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"시간표 추천 중 오류 발생: {str(e)}")


@router.post("/api/transcript/parse")
async def parse_transcript(file: UploadFile = File(...)):
    """
    [성적표 PDF 전용 파서]
    성적표 PDF에서 학번, 소속 학과, 기본 이수 요건 표 및 전체 기이수 과목 내역을 추출합니다.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        student_info, basic_credits, courses_df = extract_transcript_tokens(tmp_path)
        os.unlink(tmp_path)

        taken_courses = [
            {
                "course_code": str(row["과목코드"]),
                "name": row["교과목명"],
                "credits": int(row["학점"]),
                "grade": row["성적"],
                "area_type": row["이수구분"],
            }
            for _, row in courses_df.iterrows()
        ]

        return {
            "student_id": student_info["학번"],
            "department": student_info["소속"],
            "admission_year": int(student_info["학번"][:4]) if student_info["학번"] else 2023,
            "taken_courses": taken_courses,
            "basic_credits": basic_credits,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성적표 분석 중 오류 발생: {str(e)}")
