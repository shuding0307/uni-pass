import uuid

import pandas as pd
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models.db import Course, CourseOffering
from app.services.schedule import parse_building, parse_room


def load_courses_from_excel(file_path: str):
    print(f"Loading data from {file_path}...")
    df = pd.read_excel(file_path, header=None, engine="openpyxl")

    # 엑셀 컬럼 인덱스 (header=None, 0-based, 19열 구조)
    idx_area       = 2
    idx_code       = 3
    idx_section    = 4
    idx_name       = 5
    idx_credits    = 6
    idx_sub_area   = 11
    idx_professor  = 13
    idx_schedule   = 14   # 강의실(시간+건물+호실): "수1,2(60주년기념관 402)"
    idx_remote     = 15   # 원격수업 Y/N
    idx_cancelled  = 18   # 폐강여부 Y/N

    db = SessionLocal()
    processed_course_codes: set = set()

    try:
        count = 0
        for i in range(5, len(df)):
            row = df.iloc[i]
            try:
                code = str(row[idx_code]).strip()
                if not code or code == "nan" or len(code) < 5:
                    continue

                area_type  = str(row[idx_area]).strip()
                section    = str(row[idx_section]).strip()
                name       = str(row[idx_name]).strip().replace("\n", " ")
                sub_area   = str(row[idx_sub_area]).strip()

                credits_raw = str(row[idx_credits]).strip()
                credits_val = 3
                if "-" in credits_raw:
                    try:
                        credits_val = int(credits_raw.split("-")[0])
                    except ValueError:
                        pass

                # 강의실/시간 원본 문자열
                sched_raw = str(row[idx_schedule]).strip()
                sched_str  = sched_raw if sched_raw != "nan" else None
                professor  = str(row[idx_professor]).strip()
                professor  = professor if professor != "nan" else None
                is_remote    = str(row[idx_remote]).strip().upper() == "Y"
                is_cancelled = str(row[idx_cancelled]).strip().upper() == "Y"

                building_name = parse_building(sched_str) if sched_str else None
                room_number   = parse_room(sched_str) if sched_str else None

                # Course upsert: 기존에 없는 과목만 새로 생성
                if code not in processed_course_codes:
                    existing_course = db.query(Course).filter(Course.course_code == code).first()
                    if not existing_course:
                        db.add(Course(
                            course_code=code,
                            name=name,
                            credits=credits_val,
                            area_type=area_type,
                            sub_area=sub_area if sub_area != "nan" else None,
                            is_active=True,
                        ))
                        db.flush()
                    processed_course_codes.add(code)

                # CourseOffering upsert: 존재하면 누락 필드 백필, 없으면 새로 생성
                existing = (
                    db.query(CourseOffering)
                    .filter(
                        CourseOffering.course_code == code,
                        CourseOffering.semester == "2026-1",
                        CourseOffering.section == section,
                    )
                    .first()
                )
                if existing:
                    existing.professor     = professor
                    existing.schedule      = sched_str
                    existing.building_name = building_name
                    existing.room_number   = room_number
                    existing.raw_classroom = sched_str
                    existing.is_remote     = is_remote
                    existing.is_cancelled  = is_cancelled
                else:
                    db.add(CourseOffering(
                        id=uuid.uuid4(),
                        course_code=code,
                        semester="2026-1",
                        section=section,
                        professor=professor,
                        schedule=sched_str,
                        building_name=building_name,
                        room_number=room_number,
                        raw_classroom=sched_str,
                        is_remote=is_remote,
                        is_cancelled=is_cancelled,
                    ))

                count += 1
                if count % 200 == 0:
                    db.commit()
                    print(f"  Processed {count} rows...")

            except Exception as e:
                db.rollback()
                print(f"  [WARN] row {i} skipped: {e}")
                continue

        db.commit()
        print(f"Done. Total rows processed: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    load_courses_from_excel("data/courses_list_2026_1.xlsx")
