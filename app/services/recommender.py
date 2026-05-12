from sqlalchemy.orm import Session
from app.models.db import Course, CourseOffering
from typing import List, Dict

class RecommenderService:
    def __init__(self, db: Session):
        self.db = db

    def recommend_courses(self, deficiency_map: Dict[str, str], department: str = None) -> Dict[str, List[Dict]]:
        """
        부족한 학점 내역(deficiency_map)을 바탕으로 추천 과목 리스트를 반환합니다.
        """
        recommendations = {}

        for key, message in deficiency_map.items():
            # 1. 기초교양 필수 영역 추천 (사고와표현, 글로벌의사소통 등)
            if key.startswith("기초교양_"):
                category = key.replace("기초교양_", "")
                recommendations[key] = self._find_ge_by_category(category)

            # 2. 균형교양 부문 추천 (인간과문화, 사회와세계 등)
            elif key.startswith("균형교양_"):
                area = key.replace("균형교양_", "")
                recommendations[key] = self._find_balanced_ge_by_area(area)

            # 3. 전공 추천 (전공필수, 전공선택)
            elif key in ["전공필수", "전공선택"]:
                recommendations[key] = self._find_major_courses(key, department)

            # 4. 꿈-설계 추천
            elif key == "필수_꿈설계":
                recommendations[key] = self._find_courses_by_keyword("꿈-설계", department)

        return recommendations

    def _find_ge_by_category(self, category: str):
        # 1. 먼저 sub_area에서 매칭되는 것이 있는지 찾음 (공백 제거 후 비교)
        from sqlalchemy import func
        search_term = category.replace(" ", "")
        courses = self.db.query(Course).filter(
            Course.area_type.contains("기초"),
            func.replace(Course.sub_area, " ", "").contains(search_term)
        ).limit(3).all()
        
        if courses:
            return [self._format_course(c) for c in courses]

        # 2. 없으면 키워드로 검색
        category_keywords = {
            "사고와표현": ["창의적글쓰기", "학술적글쓰기", "대학글쓰기"],
            "글로벌의사소통": ["기본영어", "고급영어", "글로벌의사소통"],
            "디지털리터러시": ["컴퓨팅사고력", "파이썬", "인공지능", "디지털리터러시"],
            "지속가능성": ["지속가능발전"]
        }
        
        keywords = category_keywords.get(category, [])
        return self._find_courses_by_keywords(keywords)

    def _find_balanced_ge_by_area(self, area: str):
        # DB에서 sub_area가 일치하는 균형교양 과목 검색 (공백 제거 후 비교)
        from sqlalchemy import func
        search_term = area.replace(" ", "")
        
        # 1. sub_area 매칭 시도
        courses = self.db.query(Course).filter(
            Course.area_type.contains("균형"),
            func.replace(Course.sub_area, " ", "").contains(search_term)
        ).limit(3).all()
        
        if courses:
            return [self._format_course(c) for c in courses]
            
        # 2. 실패 시, 해당 키워드가 이름에 포함된 균형교양 검색
        courses = self.db.query(Course).filter(
            Course.area_type.contains("균형"),
            Course.name.contains(search_term[:2]) # 앞 두 글자만으로 검색 (예: '인간')
        ).limit(3).all()
        
        if courses:
            return [self._format_course(c) for c in courses]
            
        # 3. 그것도 없으면 그냥 균형교양 아무거나 추천
        courses = self.db.query(Course).filter(
            Course.area_type.contains("균형")
        ).limit(3).all()
        
        return [self._format_course(c) for c in courses]

    def _find_major_courses(self, area_type: str, department: str = None):
        # 학과 이름이 주어졌다면, sub_area에 학과 이름이 포함된 전공만 검색
        query = self.db.query(Course).filter(Course.area_type.contains(area_type))
        
        if department:
            # "컴퓨터공학과" 같은 텍스트에서 "컴퓨터" 정도만 추출해서 검색 정확도 높이기
            dept_keyword = department[:3] 
            query = query.filter(Course.sub_area.contains(dept_keyword))
            
        courses = query.limit(3).all()
        return [self._format_course(c) for c in courses]

    def _find_courses_by_keyword(self, keyword: str, department: str = None):
        query = self.db.query(Course).filter(Course.name.contains(keyword))
        
        if department:
            # 꿈-설계의 경우 sub_area에 학과명이 기록되어 있음
            dept_keyword = department[:3]
            query = query.filter(Course.sub_area.contains(dept_keyword))
            
        courses = query.limit(3).all()
        return [self._format_course(c) for c in courses]

    def _find_courses_by_keywords(self, keywords: List[str]):
        if not keywords: return []
        
        # 여러 키워드 중 하나라도 포함된 과목 검색
        from sqlalchemy import or_
        filters = [Course.name.contains(k) for k in keywords]
        courses = self.db.query(Course).filter(or_(*filters)).limit(3).all()
        return [self._format_course(c) for c in courses]

    def _format_course(self, course: Course):
        # 실제 개설 정보(요일, 시간 등)도 함께 가져오면 좋음
        offerings = self.db.query(CourseOffering).filter(
            CourseOffering.course_code == course.course_code
        ).limit(3).all() # 분반 정보도 최대 3개만!
        
        return {
            "course_code": course.course_code,
            "name": course.name,
            "credits": course.credits,
            "area_type": course.area_type,
            "sub_area": course.sub_area,
            "sections": [
                {
                    "section": o.section,
                    "professor": o.professor,
                    "schedule": o.schedule,
                    "classroom": o.raw_classroom
                } for o in offerings
            ]
        }
