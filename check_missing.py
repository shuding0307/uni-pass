from app.core.database import SessionLocal
from app.models.db import Course
import json

db = SessionLocal()
try:
    names = ['인간관계와 사랑', '의료AI-MLOps구축 및 실습', 'AI개론']
    results = {}
    for n in names:
        # Search for courses that contain a part of the name
        search_term = n.replace(" ", "")[:4]
        courses = db.query(Course).filter(Course.name.contains(search_term)).all()
        results[n] = [{"name": c.name, "code": c.course_code, "area": c.area_type} for c in courses]
        
    with open('missing_courses_db.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
finally:
    db.close()
