from app.services.checkers.base import RuleChecker
from app.services.checkers.context import ValidationContext
from app.services.rules import GraduationRuleSet


class GeOverflowChecker(RuleChecker):
    """교양 초과 학점을 자유선택으로 이월합니다 (입학년도별 상한선 적용)."""

    def check(self, ctx: ValidationContext) -> None:
        limit = GraduationRuleSet.ge_overflow_limit(ctx.transcript.admission_year)
        remaining = limit

        ge_areas = {
            "기초교양": ctx.req.general_education.기초교양,
            "균형교양": ctx.req.general_education.균형교양,
            "학문기초": ctx.req.general_education.학문기초,
            "특화교양": ctx.req.general_education.특화교양,
            "대교": ctx.req.general_education.대교,
        }

        for area, required in ge_areas.items():
            if required <= 0:
                continue
            taken = ctx.buckets[area]
            if taken <= required:
                continue

            excess = taken - required
            ctx.buckets[area] = required

            if remaining is None:
                ctx.buckets["자유선택"] += excess
                continue

            to_free = min(excess, remaining)
            ctx.buckets["자유선택"] += to_free
            remaining -= to_free
