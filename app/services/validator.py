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
        
        # 전공 과목 코드 세트 (검색 최적화)
        major_codes = set(getattr(self.req, 'major_course_codes', []))

        for course in passed_courses:
            area = course.area_type
            # 타 학과 수업이라도 과목코드가 같으면 전공으로 인정
            if course.course_code in major_codes:
                if area not in ["전공필수", "전공선택"]:
                    area = "전공선택"

            if area in self.buckets:
                self.buckets[area] += course.credits
            else:
                self.buckets["자유선택"] += course.credits

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
        # 규칙: 
        #   1. 영역별 목표 학점 초과분은 '자유선택'으로 인정
        #   2. 단, '영역별 목표 + 10학점'을 초과하는 학점은 졸업 학점 미포함 (증발)
        ge_areas = ["기초교양", "균형교양"]
        ge_requirements = {
            "기초교양": self.req.general_education.기초교양,
            "균형교양": self.req.general_education.균형교양
        }

        for area in ge_areas:
            required = ge_requirements[area]
            taken = self.buckets[area]
            
            if taken > required:
                excess = taken - required
                # 최대 +10학점까지만 자선으로 인정 가능
                to_free_choice = min(excess, 10)
                vaporized = excess - to_free_choice
                
                # 바구니 조정
                self.buckets[area] = required
                self.buckets["자유선택"] += to_free_choice
                
                if vaporized > 0:
                    print(f"[{area}] 인정 범위(+10)를 초과한 {vaporized}학점이 졸업 학점에서 제외(증발)되었습니다.")

        # 4. 부족한 학점 계산
        if self.buckets["전공필수"] < self.req.major_base.최소전공_필수:
            self.deficiency_map["전공필수"] = self.req.major_base.최소전공_필수 - self.buckets["전공필수"]
        
        # 5. 세부 룰(꿈 설계, 기초교양) 검사 실행
        self._check_special_requirements()

        # 총 학점(130) 계산
        total_valid_credits = sum(self.buckets.values())
        if total_valid_credits < self.req.total_credits:
            self.deficiency_map["총학점"] = self.req.total_credits - total_valid_credits

        return {
            "is_graduatable": len(self.deficiency_map) == 0,
            "buckets_status": self.buckets,
            "deficiency_map": self.deficiency_map,
            "total_valid_credits": total_valid_credits
        }
    
    
    def _check_special_requirements(self):
        """특정 필수 과목(꿈-설계, 기초교양 영역) 이수 여부를 핀셋 검사합니다."""
        # F학점을 제외한 유효한 이수 과목들만 모아둠
        # F학점(Fail), NP(Non-Pass), U(Unsatisfactory - 실격) 등 학점이 안 나오는 성적을 모두 블랙리스트 처리!
        fail_grades = {"F", "NP", "U", "FA"} # (FA는 출석 미달 F를 뜻하는 학교도 있어서 추가해두면 좋습니다)
        passed_courses = [c for c in self.transcript.taken_courses if c.grade not in fail_grades]
        taken_course_names = [c.name for c in passed_courses]

        # ---------------------------------------------------------
        # 1. 꿈-설계 룰 (2과목 이상 이수)
        # ---------------------------------------------------------
        dream_courses_count = sum(1 for name in taken_course_names if "꿈-설계" in name)
        
        if dream_courses_count < 2:
            # 2과목을 못 채웠으면 부족한 항목에 추가!
            self.deficiency_map["필수_꿈설계"] = f"2과목 이상 이수 필요 (현재 {dream_courses_count}과목 이수)"

        # ---------------------------------------------------------
        # 2. 기초교양 필수 4대 영역 룰
        # ---------------------------------------------------------
        # 나중에는 DB에서 영역 코드로 매핑하면 좋지만, 
        # 당장 MVP 버전에서는 '과목명 키워드'로 빠르고 확실하게 잡아냅니다.
        gen_ed_required_categories = {
            "사고와표현": ["창의적글쓰기", "학술적글쓰기", "사고와표현"], 
            "글로벌의사소통": ["기본영어", "고급영어", "글로벌의사소통"], 
            "디지털리터러시": ["컴퓨팅사고력", "파이썬", "인공지능", "디지털리터러시"], 
            "지속가능성": ["지속가능발전"] 
        }

        for category, keywords in gen_ed_required_categories.items():
            # 학생이 들은 전체 과목 이름 중에, 해당 카테고리의 키워드가 하나라도 포함되어 있는지 검사
            has_taken_category = any(
                any(keyword.replace(" ", "") in name.replace(" ", "") for keyword in keywords)
                for name in taken_course_names
            )
            
            if not has_taken_category:
                self.deficiency_map[f"기초교양_{category}"] = "필수 영역 미이수"

        # ---------------------------------------------------------
        # 3. 균형교양 4개 부문 필수 이수 룰 (2022학번 이후만 적용!)
        # ---------------------------------------------------------

        if self.transcript.admission_year >= 2022:
            required_balanced_areas = ["인간과문화", "사회와세계", "자연과기술", "예술과건강"]
            
            # TODO: 파싱/프론트 담당자에게 API 스펙에 'sub_area' 추가해 달라고 요청 완료하기!
            # sub_area 값이 존재하는 균형교양 과목의 부문만 띄어쓰기 없애서 수집
            taken_balanced_areas = [
                c.sub_area.replace(" ", "") for c in passed_courses 
                if c.area_type == "균형교양" and getattr(c, 'sub_area', None)
            ]
            
            for area in required_balanced_areas:
                if area not in taken_balanced_areas:
                    self.deficiency_map[f"균형교양_{area}"] = "필수 부문 미이수"
