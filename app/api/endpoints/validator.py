from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.transcript import EarnedCredit, ParsedTranscriptResponse, StudentTranscript, PlannedCourse, TakenCourse
from app.models.graduation import GraduationRequirement
from app.models.db import Course
from app.services.validator import GraduationValidator
from app.services.recommender import RecommenderService
from app.services.timetable_parser import TimetableParser
from app.services.parser import parse_graduation_requirements
from app.utils.cse_curriculum import fetch_first_available_cse_curriculum_catalog
from app.utils.earned_credit import (
    build_course_catalog,
    calculate_earned_credit,
    calculate_earned_credit_from_courses,
    get_department_course_catalog,
    get_major_credit_rules,
    graduation_requirement_to_basic_credits,
)
from app.utils.transcript_parsing import extract_transcript_tokens
from typing import Dict, Any, List
from contextlib import redirect_stdout
import io
import shutil
import os
import tempfile

# 도메인 주도 설계(DDD)를 위해 라우터 태그와 경로를 직관적으로 변경합니다.
router = APIRouter(
    tags=["Academic Agent APIs (Parsers & Evaluator)"]
)


def _extract_requirement_department(department: str | None) -> str:
    if not department:
        return "컴퓨터공학과"

    tokens = str(department).split()
    for token in reversed(tokens):
        if token.endswith(("학과", "학부", "전공")):
            return token
    return str(department).strip()


def _load_graduation_requirement(admission_year: int | None, department: str | None) -> Dict[str, Any] | None:
    if not admission_year:
        return None

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    pdf_file = os.path.join(
        base_dir,
        "data",
        "raw_requirements",
        f"이수학점표_{admission_year}학년도.pdf",
    )
    if not os.path.exists(pdf_file):
        return None

    target_department = _extract_requirement_department(department)
    with redirect_stdout(io.StringIO()):
        return parse_graduation_requirements(pdf_file, target_dept=target_department)


def _is_computer_science_department(department: str | None) -> bool:
    return "컴퓨터공학" in (department or "").replace(" ", "")


def _catalog_value(course: Any, key: str) -> Any:
    if isinstance(course, dict):
        return course.get(key)
    return getattr(course, key, None)


def _extract_admission_year(student_id: Any) -> int | None:
    if student_id and len(str(student_id)) >= 4:
        try:
            return int(str(student_id)[:4])
        except (ValueError, TypeError):
            pass
    return None


def _load_course_catalog(
    courses_df,
    db: Session,
    department: str | None,
    admission_year: int | None,
    graduation_requirement: Dict[str, Any] | None,
) -> Dict[str, Any]:
    course_codes = [
        str(code).strip()
        for code in courses_df.get("과목코드", [])
        if str(code).strip()
    ]
    matched_courses = []
    if course_codes:
        try:
            matched_courses = db.query(Course).filter(Course.course_code.in_(course_codes)).all()
        except SQLAlchemyError:
            matched_courses = []
    course_catalog = build_course_catalog(matched_courses)

    if _is_computer_science_department(department):
        curriculum_catalog = fetch_first_available_cse_curriculum_catalog(
            [admission_year, graduation_requirement.get("year") if graduation_requirement else None]
        )
        for course_code, course in curriculum_catalog.items():
            course_catalog.setdefault(course_code, course)

    fallback_catalog = get_department_course_catalog(department)
    for course_code, course in fallback_catalog.items():
        course_catalog.setdefault(course_code, course)

    return course_catalog


def _build_taken_courses(courses_df, course_catalog: Dict[str, Any], major_required_codes: set[str]) -> List[TakenCourse]:
    taken_courses = []
    for _, row in courses_df.iterrows():
        course_code = str(row["과목코드"])
        matched_course = course_catalog.get(course_code)
        matched_area_type = _catalog_value(matched_course, "area_type")
        area_type = matched_area_type or str(row.get("이수구분", "미분류"))
        if course_code in major_required_codes:
            area_type = "전공필수"
        sub_area = _catalog_value(matched_course, "sub_area")
        taken_courses.append(
            TakenCourse(
                course_code=course_code,
                name=str(row["교과목명"]),
                credits=int(row["학점"]),
                grade=str(row["성적"]),
                area_type=area_type,
                sub_area=sub_area,
            )
        )
    return taken_courses


def _parse_transcript_pdf(tmp_path: str, db: Session) -> tuple[ParsedTranscriptResponse, Dict[str, Any] | None]:
    student_info, _basic_credits, courses_df = extract_transcript_tokens(tmp_path)

    student_id = student_info.get("학번")
    admission_year = _extract_admission_year(student_id)
    department = student_info.get("department")
    graduation_requirement = _load_graduation_requirement(admission_year, department)

    course_catalog = _load_course_catalog(courses_df, db, department, admission_year, graduation_requirement)
    major_credit_rules = get_major_credit_rules(department)
    if graduation_requirement:
        major_credit_rules["major_required_limit"] = graduation_requirement["major_base"]["최소전공_필수"]
        major_credit_rules["major_elective_limit"] = graduation_requirement["major_base"]["최소전공_선택"]
        basic_credits = graduation_requirement_to_basic_credits(graduation_requirement)
    else:
        basic_credits = graduation_requirement_to_basic_credits(None)

    earned_credit = calculate_earned_credit(
        courses_df,
        course_catalog,
        major_required_codes=major_credit_rules["major_required_codes"],
        major_required_limit=major_credit_rules["major_required_limit"],
        major_elective_limit=major_credit_rules["major_elective_limit"],
        apply_major_cascade=True,
    )
    taken_courses = _build_taken_courses(
        courses_df,
        course_catalog,
        major_credit_rules["major_required_codes"],
    )
    total_earned_credits = student_info.get("총취득학점")

    return (
        ParsedTranscriptResponse(
            student_name=student_info.get("이름"),
            student_id=str(student_id) if student_id else None,
            department=department,
            admission_year=admission_year,
            total_earned_credits=int(total_earned_credits) if total_earned_credits is not None else None,
            earned_credit=earned_credit,
            basic_credits=basic_credits,
            taken_courses=taken_courses,
        ),
        graduation_requirement,
    )


def _build_planned_courses(matched_courses: List[Dict[str, Any]]) -> List[PlannedCourse]:
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


def _parse_timetable_pdf(tmp_path: str, db: Session, department: str | None) -> List[PlannedCourse]:
    parser = TimetableParser(db)
    return _build_planned_courses(parser.parse_pdf(tmp_path, department))


def _major_credit_rules_for_response(
    department: str | None,
    graduation_requirement: Dict[str, Any] | None,
) -> Dict[str, Any]:
    major_credit_rules = get_major_credit_rules(department)
    if graduation_requirement:
        major_credit_rules["major_required_limit"] = graduation_requirement["major_base"]["최소전공_필수"]
        major_credit_rules["major_elective_limit"] = graduation_requirement["major_base"]["최소전공_선택"]
    return major_credit_rules


def _attach_planned_courses(
    parsed_transcript: ParsedTranscriptResponse,
    planned_courses: List[PlannedCourse],
    graduation_requirement: Dict[str, Any] | None,
) -> ParsedTranscriptResponse:
    if not planned_courses:
        return parsed_transcript

    major_credit_rules = _major_credit_rules_for_response(parsed_transcript.department, graduation_requirement)
    earned_credit = calculate_earned_credit_from_courses(
        [*parsed_transcript.taken_courses, *planned_courses],
        major_required_codes=major_credit_rules["major_required_codes"],
        major_required_limit=major_credit_rules["major_required_limit"],
        major_elective_limit=major_credit_rules["major_elective_limit"],
        apply_major_cascade=True,
    )
    return parsed_transcript.model_copy(
        update={
            "planned_courses": planned_courses,
            "earned_credit": EarnedCredit(**earned_credit),
            "total_earned_credits": earned_credit["total"],
        }
    )


def _build_student_transcript(parsed_transcript: ParsedTranscriptResponse) -> StudentTranscript:
    return StudentTranscript(
        student_id=parsed_transcript.student_id or "",
        admission_year=parsed_transcript.admission_year or 0,
        taken_courses=parsed_transcript.taken_courses,
        planned_courses=parsed_transcript.planned_courses,
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

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        parser = TimetableParser(db)
        matched_courses = parser.parse_pdf(tmp_path, department)
        
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
    finally:
        await file.close()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

@router.post("/api/transcript/parse", response_model=ParsedTranscriptResponse)
async def parse_transcript(
    file: UploadFile = File(...),
    timetable_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> ParsedTranscriptResponse:
    """
    [성적표 PDF 전용 파서]
    성적표 PDF 파일로부터 학번, 소속 학과, 기본 이수 요건 표 및 전체 기이수 과목 내역을 추출합니다.
    시간표 PDF를 함께 업로드하면 planned_courses에 현재 수강 과목도 함께 담아 반환합니다.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="성적표는 PDF 파일만 업로드 가능합니다.")
    if timetable_file and timetable_file.filename and not timetable_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="시간표는 PDF 파일만 업로드 가능합니다.")

    tmp_path = None
    timetable_tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        parsed_transcript, graduation_requirement = _parse_transcript_pdf(tmp_path, db)
        planned_courses = []
        if timetable_file and timetable_file.filename:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                shutil.copyfileobj(timetable_file.file, tmp)
                timetable_tmp_path = tmp.name

            planned_courses = _parse_timetable_pdf(timetable_tmp_path, db, parsed_transcript.department)
            parsed_transcript = _attach_planned_courses(parsed_transcript, planned_courses, graduation_requirement)

        return parsed_transcript
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성적표 분석 중 오류 발생: {str(e)}")
    finally:
        await file.close()
        if timetable_file:
            await timetable_file.close()
        for path in [tmp_path, timetable_tmp_path]:
            if path and os.path.exists(path):
                os.unlink(path)


@router.post("/api/graduation/evaluate/files")
async def evaluate_graduation_from_files(
    transcript_file: UploadFile = File(...),
    timetable_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    """
    [파일 업로드 기반 졸업 사정]
    프론트가 성적표 PDF와 선택적으로 시간표 PDF만 업로드하면 성적표 파싱, 요건 로드, 시간표 파싱,
    졸업 사정 및 추천까지 한 번에 수행합니다.
    """
    if not transcript_file.filename or not transcript_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="성적표는 PDF 파일만 업로드 가능합니다.")
    if timetable_file and timetable_file.filename and not timetable_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="시간표는 PDF 파일만 업로드 가능합니다.")

    transcript_tmp_path = None
    timetable_tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(transcript_file.file, tmp)
            transcript_tmp_path = tmp.name

        parsed_transcript, graduation_requirement = _parse_transcript_pdf(transcript_tmp_path, db)
        if not graduation_requirement:
            raise HTTPException(status_code=400, detail="입학년도와 학과에 맞는 졸업 이수 요건을 찾을 수 없습니다.")

        planned_courses = []
        if timetable_file and timetable_file.filename:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                shutil.copyfileobj(timetable_file.file, tmp)
                timetable_tmp_path = tmp.name

            planned_courses = _parse_timetable_pdf(timetable_tmp_path, db, parsed_transcript.department)
            parsed_transcript = _attach_planned_courses(parsed_transcript, planned_courses, graduation_requirement)

        transcript = _build_student_transcript(parsed_transcript)
        requirement = GraduationRequirement(**graduation_requirement)

        validator = GraduationValidator(requirement, transcript)
        analysis_result = validator.analyze()

        try:
            recommender = RecommenderService(db)
            recommendations = recommender.recommend_courses(
                analysis_result["deficiency_map"],
                department=requirement.department,
            )
        except SQLAlchemyError:
            recommendations = {}

        return {
            "parsed_transcript": parsed_transcript,
            "planned_courses": planned_courses,
            "requirement": requirement,
            "analysis": analysis_result,
            "recommendations": recommendations,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 기반 졸업 사정 중 오류 발생: {str(e)}")
    finally:
        await transcript_file.close()
        if timetable_file:
            await timetable_file.close()
        for path in [transcript_tmp_path, timetable_tmp_path]:
            if path and os.path.exists(path):
                os.unlink(path)
