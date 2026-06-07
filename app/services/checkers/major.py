from app.services.checkers.base import RuleChecker
from app.services.checkers.context import ValidationContext


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
