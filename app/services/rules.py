class GraduationRuleSet:
    """입학년도별 졸업 규정 상수를 단일 모듈로 관리합니다."""

    BALANCED_AREAS = ["인간과문화", "사회와세계", "자연과기술", "예술과건강"]
    FAIL_GRADES = {"F", "NP", "U", "FA"}
    COURSE_LOAD_WARNINGS = (
        (22, "⚠️ 과도한 학점입니다! 학습 부하가 매우 높을 것으로 예상됩니다."),
        (19, "조금 빡빡한 일정입니다. 건강 관리에 유의하세요!"),
    )

    AREA_MAP = {
        "기초": "기초교양",
        "기교": "기초교양",
        "교약": "기초교양",
        "교필": "기초교양",
        "균형": "균형교양",
        "균교": "균형교양",
        "학문": "학문기초",
        "특화": "특화교양",
        "특교": "특화교양",
        "대교": "대교",
        "전필": "전공필수",
        "전선": "전공선택",
        "심화": "심화전공",
        "심전": "심화전공",
        "자선": "자유선택",
        "일선": "일반선택",
        "일반선택": "자유선택",
        "교직": "교직",
        "진로": "자유선택",
        "취업": "자유선택",
        "창업": "자유선택",
        "기타": "자유선택",
    }

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

    @staticmethod
    def normalize_area(area: str) -> str:
        """성적표/시간표 원문 이수구분을 시스템 표준 이수구분으로 변환합니다."""
        return GraduationRuleSet.AREA_MAP.get(area, area)

    @staticmethod
    def course_load_message(planned_credits: int) -> str:
        """수강 예정 학점에 따른 학습 부하 메시지를 반환합니다."""
        for minimum, message in GraduationRuleSet.COURSE_LOAD_WARNINGS:
            if planned_credits >= minimum:
                return message
        return "적절한 수강 계획입니다."
