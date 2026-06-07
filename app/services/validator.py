from typing import List

from app.models.graduation import GraduationRequirement
from app.models.transcript import StudentTranscript
from app.services.checkers import (
    DetailedGeChecker,
    GeOverflowChecker,
    MajorCascadeChecker,
    RuleChecker,
    ValidationContext,
)
from app.services.rules import GraduationRuleSet


class GraduationValidator:
    def __init__(self, req: GraduationRequirement, transcript: StudentTranscript):
        self.req = req
        self.transcript = transcript
        self.buckets = {
            "전공필수": 0,
            "전공선택": 0,
            "심화전공": 0,
            "기초교양": 0,
            "균형교양": 0,
            "학문기초": 0,
            "특화교양": 0,
            "대교": 0,
            "자유선택": 0,
        }
        self.deficiency_map = {}
        self.checkers: List[RuleChecker] = [
            MajorCascadeChecker(),
            GeOverflowChecker(),
            DetailedGeChecker(),
        ]

    def analyze(self) -> dict:
        if self.transcript.admission_year < 2019:
            raise ValueError("이 시스템은 2019학번 이후 학생만 지원합니다.")

        passed_courses = [
            c for c in self.transcript.taken_courses
            if c.grade not in GraduationRuleSet.FAIL_GRADES
        ]
        planned_courses = list(getattr(self.transcript, "planned_courses", []))
        major_codes = set(getattr(self.req, "major_course_codes", []))

        for course in passed_courses + planned_courses:
            self._pour_into_bucket(course, major_codes)

        ctx = ValidationContext(
            buckets=self.buckets,
            deficiency_map=self.deficiency_map,
            passed_courses=passed_courses,
            planned_courses=planned_courses,
            req=self.req,
            transcript=self.transcript,
        )

        for checker in self.checkers[:2]:
            checker.check(ctx)

        self._calculate_deficiencies()

        for checker in self.checkers[2:]:
            checker.check(ctx)

        total_valid_credits = sum(self.buckets.values())
        if total_valid_credits < self.req.total_credits:
            self.deficiency_map["총학점"] = self.req.total_credits - total_valid_credits

        planned_credits = sum(c.credits for c in planned_courses)
        load_message = GraduationRuleSet.course_load_message(planned_credits)

        return {
            "is_graduatable": len(self.deficiency_map) == 0,
            "deficiency_map": self.deficiency_map,
            "buckets_status": self.buckets,
            "earned_credits_by_area": self.buckets,
            "total_valid_credits": total_valid_credits,
            "simulation_load": {
                "planned_credits": planned_credits,
                "message": load_message,
            },
        }

    def _calculate_deficiencies(self) -> None:
        if self.buckets["전공필수"] < self.req.major_base.최소전공_필수:
            self.deficiency_map["전공필수"] = self.req.major_base.최소전공_필수 - self.buckets["전공필수"]

        if self.buckets["전공선택"] < self.req.major_base.최소전공_선택:
            self.deficiency_map["전공선택"] = self.req.major_base.최소전공_선택 - self.buckets["전공선택"]

        primary_track = self.req.tracks.get("기본전공")
        if primary_track and self.buckets["심화전공"] < primary_track.심화전공:
            self.deficiency_map["심화전공"] = primary_track.심화전공 - self.buckets["심화전공"]

        for area, required in self._general_education_requirements().items():
            if required > 0 and self.buckets[area] < required:
                self.deficiency_map[area] = required - self.buckets[area]

        ge_total = sum(self.buckets[area] for area in self._general_education_requirements())
        if ge_total < self.req.general_education.교양계:
            self.deficiency_map["교양계"] = self.req.general_education.교양계 - ge_total

    def _pour_into_bucket(self, course, major_codes) -> None:
        area = self._normalize_area(course.area_type)
        area = self._adjust_area_by_admission_year(course, area)
        if course.course_code in major_codes and area not in ("전공필수", "전공선택"):
            area = "전공선택"
        if area in self.buckets:
            self.buckets[area] += course.credits
        else:
            self.buckets["자유선택"] += course.credits

    def _adjust_area_by_admission_year(self, course, area: str) -> str:
        course_code = str(course.course_code)
        if (
            self.transcript.admission_year <= 2021
            and self.req.general_education.대교 > 0
            and course_code.startswith("14")
        ):
            return "대교"
        return area

    def _normalize_area(self, area: str) -> str:
        return GraduationRuleSet.normalize_area(area)

    def _general_education_requirements(self) -> dict:
        ge = self.req.general_education
        return {
            "기초교양": ge.기초교양,
            "균형교양": ge.균형교양,
            "학문기초": ge.학문기초,
            "특화교양": ge.특화교양,
            "대교": ge.대교,
        }
