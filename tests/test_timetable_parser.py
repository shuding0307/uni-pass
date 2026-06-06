from sqlalchemy.exc import OperationalError

from app.services.timetable_parser import TimetableParser


class FailingQuery:
    def all(self):
        raise OperationalError("SELECT * FROM courses", {}, Exception("database unavailable"))


class FailingSession:
    def query(self, _model):
        return FailingQuery()


def test_timetable_parser_falls_back_to_csv_catalog_when_db_is_unavailable():
    parser = TimetableParser(FailingSession())

    matched_courses = parser._match_in_text("화 1 강원-인,함께여는미래 온라인", "컴퓨터공학과")

    assert matched_courses == [
        {
            "course_code": "11000001",
            "name": "강원-인,함께여는미래",
            "credits": 2,
            "area_type": "G-Share",
            "sub_area": None,
            "building_name": None,
        }
    ]


def test_timetable_parser_reads_uploaded_pdf_without_requiring_database():
    parser = TimetableParser(FailingSession())

    matched_courses = parser.parse_pdf("data/시간표.pdf", "컴퓨터공학과")

    assert [course["name"] for course in matched_courses] == [
        "운영체제",
        "생성형AI프로젝트",
        "소프트웨어공학",
        "LLMOps파인튜닝및배포실습",
        "데이터베이스프로그래밍",
        "캡스톤디자인",
    ]
