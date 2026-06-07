from app.services.checkers.base import RuleChecker
from app.services.checkers.context import ValidationContext
from app.services.rules import GraduationRuleSet


class DetailedGeChecker(RuleChecker):
    """꿈-설계 필수, 기초교양 세부영역, 균형교양 4부문 이수 여부를 검사합니다."""

    def check(self, ctx: ValidationContext) -> None:
        all_courses = ctx.passed_courses + list(ctx.planned_courses)

        if ctx.transcript.admission_year >= 2018:
            dream = [c for c in all_courses if "꿈-설계" in c.name]
            dream_credits = sum(c.credits for c in dream)
            if len(dream) < 2 or dream_credits < 2:
                ctx.deficiency_map["필수_꿈설계"] = max(2 - len(dream), 2 - dream_credits)

        rules = GraduationRuleSet.basic_ge_rules(ctx.transcript.admission_year)
        for area, rule in rules.items():
            area_credits = sum(
                c.credits for c in all_courses
                if any(k in c.name for k in rule["keywords"])
            )
            if area_credits < rule["target"]:
                ctx.deficiency_map[f"기초교양_{area}"] = rule["target"] - area_credits

        if ctx.transcript.admission_year >= 2022:
            for area in GraduationRuleSet.BALANCED_AREAS:
                has_taken = any(
                    (getattr(c, "sub_area", None) and area in c.sub_area.replace(" ", ""))
                    or (area[:2] in c.name)
                    for c in all_courses
                    if "균형" in c.area_type
                )
                if not has_taken:
                    ctx.deficiency_map[f"균형교양_{area}"] = 1
