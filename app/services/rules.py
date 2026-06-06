class GraduationRuleSet:
    """입학년도별 졸업 규정 상수를 단일 모듈로 관리합니다."""

    BALANCED_AREAS = ["인간과문화", "사회와세계", "자연과기술", "예술과건강"]

    # Recommender에서 기초교양 세부영역 키워드 검색에 사용
    CATEGORY_SEARCH_KEYWORDS = {
        "사고와표현": ["창의적글쓰기", "학술적글쓰기", "대학글쓰기"],
        "글로벌의사소통": ["기본영어", "고급영어", "글로벌의사소통"],
        "디지털리터러시": ["컴퓨팅사고력", "파이썬", "인공지능", "디지털리터러시"],
        "지속가능성": ["지속가능발전"],
    }

    @staticmethod
    def basic_ge_rules(admission_year: int) -> dict:
        """입학년도별 기초교양 세부영역 검사 룰을 반환합니다."""
        rules = {
            "사고와표현": {
                "keywords": ["글쓰기와말하기", "창의적글쓰기", "학술적글쓰기", "대학글쓰기", "사고와표현"],
                "target": 3,
            },
            "글로벌의사소통": {
                "keywords": ["의사소통영어", "영어", "외국어", "글로벌의사소통"],
                "target": 4 if admission_year <= 2021 else 6,
            },
            "디지털리터러시": {
                "keywords": ["컴퓨팅사고력", "컴퓨팅", "파이썬", "인공지능", "디지털리터러시"],
                "target": 3 if admission_year <= 2021 else 6,
            },
        }
        if admission_year >= 2022:
            rules["지속가능성"] = {
                "keywords": ["지속가능발전"],
                "target": 2,
            }
        return rules

    @staticmethod
    def ge_overflow_limit(admission_year: int):
        """교양 초과 학점 중 자유선택으로 인정되는 최대 학점을 반환합니다. 제한 없으면 None."""
        if admission_year <= 2004:
            return None
        return 10
