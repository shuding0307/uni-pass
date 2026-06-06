from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class ValidationContext:
    buckets: Dict[str, int]
    deficiency_map: Dict[str, Any]
    passed_courses: List
    planned_courses: List
    req: Any       # GraduationRequirement
    transcript: Any  # StudentTranscript


class RuleChecker(ABC):
    @abstractmethod
    def check(self, ctx: ValidationContext) -> None:
        ...


class MajorCascadeChecker(RuleChecker):
    """전필 초과 학점을 전선 → 심화전공 순으로 이월합니다."""

    def check(self, ctx: ValidationContext) -> None:
        req = ctx.req
        if ctx.buckets["전공필수"] > req.major_base.최소전공_필수:
            overflow = ctx.buckets["전공필수"] - req.major_base.최소전공_필수
            ctx.buckets["전공필수"] = req.major_base.최소전공_필수
            ctx.buckets["전공선택"] += overflow

        if ctx.buckets["전공선택"] > req.major_base.최소전공_선택:
            overflow = ctx.buckets["전공선택"] - req.major_base.최소전공_선택
            ctx.buckets["전공선택"] = req.major_base.최소전공_선택
            ctx.buckets["심화전공"] += overflow


class GeOverflowChecker(RuleChecker):
    """교양 초과 학점을 자유선택으로 이월합니다 (입학년도별 상한선 적용)."""

    def check(self, ctx: ValidationContext) -> None:
        from app.services.rules import GraduationRuleSet
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


class DetailedGeChecker(RuleChecker):
    """꿈-설계 필수, 기초교양 세부영역, 균형교양 4부문 이수 여부를 검사합니다."""

    def check(self, ctx: ValidationContext) -> None:
        from app.services.rules import GraduationRuleSet
        all_courses = ctx.passed_courses + list(ctx.planned_courses)

        # 1. 꿈-설계 (2018학번 이상)
        if ctx.transcript.admission_year >= 2018:
            dream = [c for c in all_courses if "꿈-설계" in c.name]
            dream_credits = sum(c.credits for c in dream)
            if len(dream) < 2 or dream_credits < 2:
                ctx.deficiency_map["필수_꿈설계"] = max(2 - len(dream), 2 - dream_credits)

        # 2. 기초교양 세부영역 (입학년도별 룰셋)
        rules = GraduationRuleSet.basic_ge_rules(ctx.transcript.admission_year)
        for area, rule in rules.items():
            area_credits = sum(
                c.credits for c in all_courses
                if any(k in c.name for k in rule["keywords"])
            )
            if area_credits < rule["target"]:
                ctx.deficiency_map[f"기초교양_{area}"] = rule["target"] - area_credits

        # 3. 균형교양 4부문 (2022학번 이상)
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
