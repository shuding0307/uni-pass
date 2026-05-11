import pandas as pd
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, init_db
from app.models.db import Course, CourseOffering
import uuid

def load_courses_from_excel(file_path: str):
    print(f"Loading data from {file_path}...")
    df = pd.read_excel(file_path, header=None)
    
    # Manual Mapping for this specific file structure
    idx_area = 2
    idx_code = 3
    idx_section = 4
    idx_name = 5
    idx_credits = 6
    idx_sub_area = 11
    idx_professor = 13 # Often name is in a different place or combined
    idx_classroom = 13

    db = SessionLocal()
    processed_course_codes = set()
    
    try:
        count = 0
        for i in range(5, len(df)):
            row = df.iloc[i]
            try:
                code = str(row[idx_code]).strip()
                if not code or code == 'nan' or len(code) < 5:
                    continue
                
                area_type = str(row[idx_area]).strip()
                section = str(row[idx_section]).strip()
                name = str(row[idx_name]).strip()
                sub_area = str(row[idx_sub_area]).strip()
                
                # Credits (e.g., '3-3-0-0')
                credits_raw = str(row[idx_credits]).strip()
                credits_val = 3
                if '-' in credits_raw:
                    credits_val = int(credits_raw.split('-')[0])
                
                name = name.replace('\n', ' ')
                
                if code not in processed_course_codes:
                    existing_course = db.query(Course).filter(Course.course_code == code).first()
                    if not existing_course:
                        course = Course(
                            course_code=code,
                            name=name,
                            credits=credits_val,
                            area_type=area_type, 
                            sub_area=sub_area if sub_area != 'nan' else None,
                            is_active=True
                        )
                        db.add(course)
                        db.flush()
                    processed_course_codes.add(code)
                
                existing_offering = db.query(CourseOffering).filter(
                    CourseOffering.course_code == code,
                    CourseOffering.semester == "2026-1",
                    CourseOffering.section == section
                ).first()

                if not existing_offering:
                    offering = CourseOffering(
                        id=uuid.uuid4(),
                        course_code=code,
                        semester="2026-1",
                        section=section,
                        # For now, put the whole string in raw_classroom
                        raw_classroom=str(row[idx_classroom]).strip() if str(row[idx_classroom]) != 'nan' else None
                    )
                    db.add(offering)
                
                count += 1
                if count % 100 == 0:
                    db.commit()
                    print(f"Processed {count} rows...")
                    
            except Exception as e:
                db.rollback()
                continue
                
        db.commit()
        print(f"Successfully loaded {count} course offerings.")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    load_courses_from_excel('data/courses_list_2026_1.xlsx')
