from app.models.graduation import GraduationRequirement
from app.models.transcript import StudentTranscript

class GraduationValidator:
    def __init__(self, req: GraduationRequirement, transcript: StudentTranscript):
        self.req = req
        self.transcript = transcript
        # 학점을 담을 바구니 초기화
        self.buckets = {
            "전공필수": 0, "전공선택": 0, "심화전공": 0, 
            "기초교양": 0, "균형교양": 0, "자유선택": 0
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

        # 3. 교양 초과 학점 처리 (2014학번 이후 기준)
        ge_requirements = {
            "기초교양": self.req.general_education.기초교양,
            "균형교양": self.req.general_education.균형교양
        }

        for area in ["기초교양", "균형교양"]:
            required = ge_requirements[area]
            taken = self.buckets[area]
            
            if taken > required:
                excess = taken - required
                to_free_choice = min(excess, 10)
                # 바구니 조정
                self.buckets[area] = required
                self.buckets["자유선택"] += to_free_choice

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
        if self.buckets["기초교양"] < self.req.general_education.기초교양:
            self.deficiency_map["기초교양"] = self.req.general_education.기초교양 - self.buckets["기초교양"]
            
        if self.buckets["균형교양"] < self.req.general_education.균형교양:
            self.deficiency_map["균형교양"] = self.req.general_education.균형교양 - self.buckets["균형교양"]

        # 5. 세부 마이크로 룰 (교양 필수 영역 등) 검사
        self._check_detailed_requirements(passed_courses)

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
        area = course.area_type
        # 타 학과 수업이라도 과목코드가 같으면 전공으로 인정
        if course.course_code in major_codes:
            if area not in ["전공필수", "전공선택"]:
                area = "전공선택"

        if area in self.buckets:
            self.buckets[area] += course.credits
        else:
            self.buckets["자유선택"] += course.credits

    def _check_detailed_requirements(self, passed_courses):
        """특정 필수 영역의 학점 및 이수 여부를 정밀 검사합니다."""
        taken_course_names = [c.name for c in passed_courses]

        # 1. 꿈-설계 (2과목 이상)
        dream_count = sum(1 for name in taken_course_names if "꿈-설계" in name)
        if dream_count < 2:
            self.deficiency_map["필수_꿈설계"] = 2 - dream_count

        # 2. 기초교양 4대 영역 (사고 3, 글로벌 6, 디지털 6, 지속가능 2)
        # ※ 실제 학점표에 기초교양 총점이 17인 경우 등을 고려하여 목표값 설정
        basic_ge_rules = {
            "사고와표현": {"keywords": ["창의적글쓰기", "학술적글쓰기", "대학글쓰기", "사고와표현"], "target": 3},
            "글로벌의사소통": {"keywords": ["영어", "외국어", "글로벌의사소통"], "target": 6},
            "디지털리터러시": {"keywords": ["컴퓨팅", "파이썬", "인공지능", "디지털리터러시"], "target": 6},
            "지속가능성": {"keywords": ["지속가능발전"], "target": 2}
        }

        for area, rule in basic_ge_rules.items():
            # 해당 영역 과목들의 학점 합계 계산
            area_credits = sum(
                c.credits for c in passed_courses
                if any(k in c.name for k in rule["keywords"])
            )
            if area_credits < rule["target"]:
                self.deficiency_map[f"기초교양_{area}"] = rule["target"] - area_credits

        # 3. 균형교양 4개 부문 (각 1과목 이상 필수, 2022학번 이후)
        if self.transcript.admission_year >= 2022:
            balanced_areas = ["인간과문화", "사회와세계", "자연과기술", "예술과건강"]
            # sub_area 또는 이름을 통해 부문 판별
            for area in balanced_areas:
                has_taken = any(
                    (c.sub_area and area in c.sub_area.replace(" ", "")) or (area[:2] in c.name)
                    for c in passed_courses if "균형" in c.area_type
                )
                if not has_taken:
                    # 부문은 과목 수 기준이므로 '1'로 표시 (미이수 1개 부문)
                    self.deficiency_map[f"균형교양_{area}"] = 1
