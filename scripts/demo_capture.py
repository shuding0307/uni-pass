import argparse
import contextlib
import io
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.database import SessionLocal
from app.models.db import Course, CourseOffering
from app.models.graduation import GraduationRequirement
from app.models.transcript import PlannedCourse, StudentTranscript, TakenCourse
from app.services.parser import parse_graduation_requirements
from app.services.timetable_parser import TimetableParser
from app.services.validator import GraduationValidator
from app.utils.transcript_parsing import extract_transcript_tokens


TRANSCRIPT_PDF = ROOT / "test_data" / "grade.pdf"
TIMETABLE_PDF = ROOT / "test_data" / "kcloud.pdf"
REQUIREMENT_YEAR = "2021"
REQUIREMENT_PDF = ROOT / "data" / "raw_requirements" / f"이수학점표_{REQUIREMENT_YEAR}학년도.pdf"


def title(text: str) -> None:
    print()
    print("=" * 72)
    print(text)
    print("=" * 72)


def section(text: str) -> None:
    print()
    print(f"[{text}]")
    print("-" * 72)


def print_table(headers: list[str], rows: Iterable[Iterable[object]], limit: int | None = None) -> None:
    rows = [list(map(lambda v: "" if v is None else str(v), row)) for row in rows]
    if limit is not None:
        rows = rows[:limit]

    widths = [len(h) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len(value))

    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*row))


def demo_transcript():
    title("DEMO 1. 성적표 PDF 파싱")
    student_info, basic_credits, courses_df = extract_transcript_tokens(str(TRANSCRIPT_PDF))

    section("학생 정보")
    print(f"학번: {student_info.get('학번')}")
    print(f"소속: {student_info.get('소속') or 'PDF 텍스트에서 학과명 미검출'}")
    print(f"총취득학점: {student_info.get('총취득학점') or '미검출'}")
    print(f"추출 과목 수: {len(courses_df)}개")

    section("기본 이수 학점")
    print_table(["영역", "학점"], basic_credits.items())

    section("이수 과목 전체")
    rows = courses_df[["과목코드", "교과목명", "학점", "성적", "이수구분"]].values.tolist()
    print_table(["과목코드", "교과목명", "학점", "성적", "이수구분"], rows  )

    return student_info, basic_credits, courses_df


def demo_requirements() -> GraduationRequirement:
    title("DEMO 2. 졸업요건 PDF 파싱")
    with contextlib.redirect_stdout(io.StringIO()):
        parsed = parse_graduation_requirements(str(REQUIREMENT_PDF), target_dept="컴퓨터공학과")
    requirement = GraduationRequirement(**parsed)

    section(f"컴퓨터공학과 {REQUIREMENT_YEAR}학년도 졸업요건")
    print(f"졸업 총학점: {requirement.total_credits}")
    ge_rows = [
        ["기초교양", requirement.general_education.기초교양],
        ["균형교양", requirement.general_education.균형교양],
    ]
    if requirement.general_education.특화교양:
        ge_rows.append(["특화교양", requirement.general_education.특화교양])
    if requirement.general_education.대교:
        ge_rows.append(["대교", requirement.general_education.대교])
    if requirement.general_education.학문기초:
        ge_rows.append(["학문기초", requirement.general_education.학문기초])
    ge_rows.extend([
        ["교양계", requirement.general_education.교양계],
        ["전공필수", requirement.major_base.최소전공_필수],
        ["전공선택", requirement.major_base.최소전공_선택],
    ])
    default_track = requirement.tracks.get("기본전공")
    if default_track:
        ge_rows.extend([
            ["심화전공", default_track.심화전공],
            ["전공계", default_track.전공계],
            ["자유선택", default_track.자유선택],
        ])
    print_table(
        ["구분", "필요 학점"],
        ge_rows,
    )

    section("트랙별 요건")
    print_table(
        ["트랙", "심화전공", "전공계", "자유선택"],
        [
            [name, detail.심화전공, detail.전공계, detail.자유선택]
            for name, detail in requirement.tracks.items()
        ],
    )
    return requirement


def parse_timetable_courses() -> tuple[list[dict], int, int]:
    db = SessionLocal()
    try:
        course_count = db.query(Course).count()
        offering_count = db.query(CourseOffering).count()
        parser = TimetableParser(db)
        courses = parser.parse_pdf(str(TIMETABLE_PDF), department="컴퓨터공학과")
        return courses, course_count, offering_count
    finally:
        db.close()


def transcript_from_dataframe(student_info: dict, courses_df, planned_courses: list[dict] | None = None) -> StudentTranscript:
    taken_courses = [
        TakenCourse(
            course_code=str(row["과목코드"]),
            name=row["교과목명"],
            credits=int(row["학점"]),
            grade=row["성적"],
            area_type=row["이수구분"],
        )
        for _, row in courses_df.iterrows()
    ]
    planned = [
        PlannedCourse(
            course_code=str(course["course_code"]),
            name=course["name"],
            credits=int(course["credits"]),
            area_type=course["area_type"],
            building_name=course.get("building_name"),
        )
        for course in (planned_courses or [])
    ]
    student_id = student_info.get("학번") or "202111109"
    return StudentTranscript(
        student_id=student_id,
        admission_year=int(student_id[:4]),
        taken_courses=taken_courses,
        planned_courses=planned,
    )


def demo_analysis(requirement: GraduationRequirement, transcript: StudentTranscript):
    title("DEMO 4. 학점 버킷 분석")
    result = GraduationValidator(requirement, transcript).analyze()

    section("분석 입력")
    print(f"성적표 기이수 과목: {len(transcript.taken_courses)}개")
    print(f"이번 학기 시간표 반영 과목: {len(transcript.planned_courses)}개")
    print(f"이번 학기 시간표 반영 학점: {sum(course.credits for course in transcript.planned_courses)}학점")

    if transcript.planned_courses:
        print()
        print_table(
            ["구분", "과목코드", "과목명", "학점", "이수구분"],
            [
                ["이수 예정", course.course_code, course.name, course.credits, course.area_type]
                for course in transcript.planned_courses
            ],
        )

    section("영역별 인정 학점")
    print_table(["영역", "인정 학점"], result["buckets_status"].items())

    section("부족 요건")
    deficiencies = result["deficiency_map"]
    if deficiencies:
        print_table(["부족 항목", "부족 학점/개수"], deficiencies.items())
    else:
        print("부족 요건 없음")

    section("판정 요약")
    print(f"졸업 가능 여부: {'가능' if result['is_graduatable'] else '불가'}")
    print(f"총 인정 학점: {result['total_valid_credits']} / {requirement.total_credits}")
    print(f"이번 학기 계획 학점: {result['simulation_load']['planned_credits']}")
    print(f"수강 부하 메시지: {result['simulation_load']['message']}")


def demo_timetable():
    title("DEMO 3. 시간표 PDF 파싱")
    courses, course_count, offering_count = parse_timetable_courses()

    print(f"PostgreSQL 과목 마스터: {course_count}개")
    print(f"PostgreSQL 개설 분반: {offering_count}개")

    section("시간표에서 매칭된 과목")
    print_table(
        ["과목코드", "과목명", "학점", "이수구분", "건물"],
        [
            [
                course["course_code"],
                course["name"],
                course["credits"],
                course["area_type"],
                course.get("building_name") or "-",
            ]
            for course in courses
        ],
    )
    print(f"\n총 {len(courses)}개 과목 매칭")


def main():
    parser = argparse.ArgumentParser(description="PPT 캡처용 uni-pass 기능 데모 출력")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        choices=["all", "transcript", "requirements", "analysis", "timetable"],
        help="캡처할 데모 섹션",
    )
    args = parser.parse_args()

    student_info = courses_df = requirement = transcript = None

    if args.target in {"all", "transcript", "analysis"}:
        student_info, _, courses_df = demo_transcript()

    if args.target in {"all", "requirements", "analysis"}:
        requirement = demo_requirements()

    if args.target in {"all", "analysis"}:
        planned_courses, _, _ = parse_timetable_courses()
        transcript = transcript_from_dataframe(student_info, courses_df, planned_courses)
        demo_analysis(requirement, transcript)

    if args.target in {"all", "timetable"}:
        demo_timetable()


if __name__ == "__main__":
    main()
