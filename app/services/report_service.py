from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.db import Student, AnalysisResult, GraduationRequirementDB
from app.models.graduation import GraduationRequirement
from typing import List, Dict, Any


class ReportService:
    """졸업 사정 결과를 DB에 영속화하고 이력을 조회합니다."""

    def __init__(self, db: Session):
        self.db = db

    def save_result(
        self,
        student_id: str,
        admission_year: int,
        requirement: GraduationRequirement,
        analysis: dict,
    ) -> AnalysisResult | None:
        """학생·요건 레코드를 upsert하고 분석 결과를 저장합니다. DB 오류 시 None 반환."""
        try:
            self._upsert_student(student_id, admission_year, requirement.department)
            req_db = self._get_or_create_requirement(requirement, admission_year)
            result = AnalysisResult(
                student_id=student_id,
                requirement_id=req_db.id,
                result_json=analysis,
                deficiency_map=analysis.get("deficiency_map", {}),
                overflow_map={},
            )
            self.db.add(result)
            self.db.commit()
            self.db.refresh(result)
            return result
        except SQLAlchemyError:
            self.db.rollback()
            return None

    def get_history(self, student_id: str) -> List[Dict[str, Any]]:
        """학생의 과거 졸업 사정 이력을 최신순으로 반환합니다."""
        results = (
            self.db.query(AnalysisResult)
            .filter(AnalysisResult.student_id == student_id)
            .order_by(AnalysisResult.analyzed_at.desc())
            .all()
        )
        return [
            {
                "id": str(r.id),
                "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
                "is_graduatable": r.result_json.get("is_graduatable"),
                "deficiency_map": r.deficiency_map,
            }
            for r in results
        ]

    def _upsert_student(self, student_id: str, admission_year: int, major: str) -> None:
        existing = self.db.query(Student).filter(Student.student_id == student_id).first()
        if not existing:
            self.db.add(Student(
                student_id=student_id,
                name="미입력",
                major=major,
                admission_year=admission_year,
            ))
            self.db.flush()

    def _get_or_create_requirement(
        self, req: GraduationRequirement, admission_year: int
    ) -> GraduationRequirementDB:
        existing = (
            self.db.query(GraduationRequirementDB)
            .filter(
                GraduationRequirementDB.major == req.department,
                GraduationRequirementDB.admission_year == admission_year,
                GraduationRequirementDB.is_eng_cert == False,
            )
            .first()
        )
        if existing:
            return existing

        primary_track = req.tracks.get("기본전공")
        req_db = GraduationRequirementDB(
            major=req.department,
            admission_year=admission_year,
            basic_ge=req.general_education.기초교양,
            balanced_ge=req.general_education.균형교양,
            specialized_ge=req.general_education.특화교양,
            univ_core_ge=req.general_education.대교,
            major_required=req.major_base.최소전공_필수,
            major_elective=req.major_base.최소전공_선택,
            advanced_major=primary_track.심화전공 if primary_track else 0,
            general_elective=primary_track.자유선택 if primary_track else 0,
            total_credits=req.total_credits,
        )
        self.db.add(req_db)
        self.db.flush()
        return req_db
