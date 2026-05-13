from app.models.graduation import GraduationRequirement
from app.models.transcript import StudentTranscript

class GraduationValidator:
    def __init__(self, req: GraduationRequirement, transcript: StudentTranscript):
        self.req = req
        self.transcript = transcript
        # 학점을 담을 바구니 초기화
        self.buckets = {
            "전공필수": 0, "전공선택": 0, "심화전공": 0, 
            "기초교양": 0, "균형교양": 0, "학문기초": 0,
            "특화교양": 0, "대교": 0, "자유선택": 0
        }
        self.deficiency_map = {} # 부족한 학점 기록장

    def analyze(self):
        # 0. 2019학번 이상인지 체크
        if self.transcript.admission_year < 2019:
            raise ValueError("이 시스템은 2019학번 이후 학생만 지원합니다.")

        # 1. 바구니에 학점 붓기 (F학점 제외)
        fail_grades = {"F", "NP", "U", "FA"}
        passed_courses = [c for c in self.transcript.taken_courses if c.grade not in fail_grades]
        
        # [시뮬레이션 추가] 계획 중인 과목들도 분석 대상에 포함
        planned_courses = getattr(self.transcript, 'planned_courses', [])
        
        # 전공 과목 코드 세트 (검색 최적화)
        major_codes = set(getattr(self.req, 'major_course_codes', []))

        # 기이수 과목 처리
        for course in passed_courses:
            self._pour_into_bucket(course, major_codes)
            
        # 계획 과목 처리 (성적은 없으므로 무조건 통과로 간주)
        for course in planned_courses:
            self._pour_into_bucket(course, major_codes)

        # 2. 전공 폭포수 로직 (전필 -> 전선 -> 심화전공)
        if self.buckets["전공필수"] > self.req.major_base.최소전공_필수:
            overflow = self.buckets["전공필수"] - self.req.major_base.최소전공_필수
            self.buckets["전공필수"] = self.req.major_base.최소전공_필수
            self.buckets["전공선택"] += overflow

        if self.buckets["전공선택"] > self.req.major_base.최소전공_선택:
            overflow = self.buckets["전공선택"] - self.req.major_base.최소전공_선택
            self.buckets["전공선택"] = self.req.major_base.최소전공_선택
            self.buckets["심화전공"] += overflow

        # 3. 교양 초과 학점 처리
        # 2014학번 이후는 교양 초과 학점을 최대 10학점까지만 자유선택으로 인정합니다.
        self._move_general_education_overflow()

        # 4. 전체 영역별 부족 학점 계산
        # 전공 영역
        if self.buckets["전공필수"] < self.req.major_base.최소전공_필수:
            self.deficiency_map["전공필수"] = self.req.major_base.최소전공_필수 - self.buckets["전공필수"]
        
        if self.buckets["전공선택"] < self.req.major_base.최소전공_선택:
            self.deficiency_map["전공선택"] = self.req.major_base.최소전공_선택 - self.buckets["전공선택"]
            
        primary_track = self.req.tracks.get("기본전공")
        if primary_track and self.buckets["심화전공"] < primary_track.심화전공:
            self.deficiency_map["심화전공"] = primary_track.심화전공 - self.buckets["심화전공"]

        # 교양 영역
        for area, required in self._general_education_requirements().items():
            if required > 0 and self.buckets[area] < required:
                self.deficiency_map[area] = required - self.buckets[area]

        ge_total = sum(self.buckets[area] for area in self._general_education_requirements())
        if ge_total < self.req.general_education.교양계:
            self.deficiency_map["교양계"] = self.req.general_education.교양계 - ge_total

        # 5. 세부 마이크로 룰 (교양 필수 영역 등) 검사
        self._check_detailed_requirements(passed_courses + list(planned_courses))

        # 총 학점 계산
        total_valid_credits = sum(self.buckets.values())
        if total_valid_credits < self.req.total_credits:
            self.deficiency_map["총학점"] = self.req.total_credits - total_valid_credits

        # [학습 부하 관리] 이번 학기 계획 학점 분석
        planned_credits = sum(c.credits for c in planned_courses)
        load_message = "적절한 수강 계획입니다."
        if planned_credits >= 22:
            load_message = "⚠️ 과도한 학점입니다! 학습 부하가 매우 높을 것으로 예상됩니다."
        elif planned_credits >= 19:
            load_message = "조금 빡빡한 일정입니다. 건강 관리에 유의하세요!"

        return {
            "is_graduatable": len(self.deficiency_map) == 0,
            "buckets_status": self.buckets,
            "deficiency_map": self.deficiency_map,
            "total_valid_credits": total_valid_credits,
            "simulation_load": {
                "planned_credits": planned_credits,
                "message": load_message
            }
        }
    
    def _pour_into_bucket(self, course, major_codes):
        """과목을 적절한 바구니에 담습니다."""
        area = self._normalize_area(course.area_type)
        area = self._adjust_area_by_admission_year(course, area)
        # 타 학과 수업이라도 과목코드가 같으면 전공으로 인정
        if course.course_code in major_codes:
            if area not in ["전공필수", "전공선택"]:
                area = "전공선택"

        if area in self.buckets:
            self.buckets[area] += course.credits
        else:
            self.buckets["자유선택"] += course.credits

    def _adjust_area_by_admission_year(self, course, area):
        course_code = str(course.course_code)

        # 2021학년도 이전 이수학점표는 현재 학문기초로 분리되는 14번대 교과목을
        # 대교(대학별 교양) 축으로 요구하는 경우가 있습니다.
        if (
            self.transcript.admission_year <= 2021
            and self.req.general_education.대교 > 0
            and course_code.startswith("14")
        ):
            return "대교"

        return area

    def _normalize_area(self, area):
        area_map = {
            "기초": "기초교양",
            "균형": "균형교양",
            "학문": "학문기초",
            "특화": "특화교양",
            "전필": "전공필수",
            "전선": "전공선택",
            "심화": "심화전공",
            "자선": "자유선택",
            "일선": "자유선택",
            "일반선택": "자유선택",
            "교직": "자유선택",
            "진로": "자유선택",
            "취업": "자유선택",
            "창업": "자유선택",
            "기타": "자유선택",
        }
        return area_map.get(area, area)

    def _general_education_requirements(self):
        return {
            "기초교양": self.req.general_education.기초교양,
            "균형교양": self.req.general_education.균형교양,
            "학문기초": self.req.general_education.학문기초,
            "특화교양": self.req.general_education.특화교양,
            "대교": self.req.general_education.대교,
        }

    def _general_education_overflow_limit(self):
        if self.transcript.admission_year <= 2004:
            return None
        if self.transcript.admission_year >= 2005:
            return 10
        return 0

    def _move_general_education_overflow(self):
        remaining_free_choice_limit = self._general_education_overflow_limit()

        for area, required in self._general_education_requirements().items():
            if required <= 0:
                continue

            taken = self.buckets[area]
            if taken <= required:
                continue

            excess = taken - required
            self.buckets[area] = required

            if remaining_free_choice_limit is None:
                self.buckets["자유선택"] += excess
                continue

            to_free_choice = min(excess, remaining_free_choice_limit)
            self.buckets["자유선택"] += to_free_choice
            remaining_free_choice_limit -= to_free_choice

    def _check_detailed_requirements(self, passed_courses):
        """특정 필수 영역의 학점 및 이수 여부를 정밀 검사합니다."""
        taken_course_names = [c.name for c in passed_courses]

        # 1. 꿈-설계
        if self.transcript.admission_year >= 2018:
            dream_courses = [c for c in passed_courses if "꿈-설계" in c.name]
            dream_count = len(dream_courses)
            dream_credits = sum(c.credits for c in dream_courses)
            if dream_count < 2 or dream_credits < 2:
                self.deficiency_map["필수_꿈설계"] = max(2 - dream_count, 2 - dream_credits)

        # 2. 입학년도별 기초교양 세부 영역
        basic_ge_rules = self._basic_general_education_rules()

        for area, rule in basic_ge_rules.items():
            # 해당 영역 과목들의 학점 합계 계산
            area_credits = sum(
                c.credits for c in passed_courses
                if any(k in c.name for k in rule["keywords"])
            )
            if area_credits < rule["target"]:
                self.deficiency_map[f"기초교양_{area}"] = rule["target"] - area_credits

        # 3. 균형교양 4개 부문
        # 2021학번까지는 부문에 상관없이 균형교양 학점만 충족하면 됩니다.
        # 2022학번부터는 4개 부문을 각각 1과목 이상 이수해야 합니다.
        if self.transcript.admission_year >= 2022:
            balanced_areas = ["인간과문화", "사회와세계", "자연과기술", "예술과건강"]
            # sub_area 또는 이름을 통해 부문 판별
            for area in balanced_areas:
                has_taken = any(
                    (getattr(c, "sub_area", None) and area in c.sub_area.replace(" ", "")) or (area[:2] in c.name)
                    for c in passed_courses if "균형" in c.area_type
                )
                if not has_taken:
                    # 부문은 과목 수 기준이므로 '1'로 표시 (미이수 1개 부문)
                    self.deficiency_map[f"균형교양_{area}"] = 1

    def _basic_general_education_rules(self):
        if self.transcript.admission_year <= 2021:
            return {
                "사고와표현": {
                    "keywords": ["글쓰기와말하기", "창의적글쓰기", "학술적글쓰기", "대학글쓰기", "사고와표현"],
                    "target": 3,
                },
                "글로벌의사소통": {
                    "keywords": ["의사소통영어", "영어", "외국어", "글로벌의사소통"],
                    "target": 4,
                },
                "디지털리터러시": {
                    "keywords": ["컴퓨팅사고력", "컴퓨팅", "파이썬", "인공지능", "디지털리터러시"],
                    "target": 3,
                },
            }

        return {
            "사고와표현": {
                "keywords": ["글쓰기와말하기", "창의적글쓰기", "학술적글쓰기", "대학글쓰기", "사고와표현"],
                "target": 3,
            },
            "글로벌의사소통": {
                "keywords": ["의사소통영어", "영어", "외국어", "글로벌의사소통"],
                "target": 6,
            },
            "디지털리터러시": {
                "keywords": ["컴퓨팅사고력", "컴퓨팅", "파이썬", "인공지능", "디지털리터러시"],
                "target": 6,
            },
            "지속가능성": {
                "keywords": ["지속가능발전"],
                "target": 2,
            },
        }
