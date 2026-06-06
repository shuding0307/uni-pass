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

    matched_courses = parser.parse_pdf("test_data/kcloud.pdf", "컴퓨터공학과")

    assert [course["name"] for course in matched_courses] == [
        "정밀의료와AI개론",
        "인간관계와사랑",
        "소프트웨어공학",
        "의료AI-MLOps구축및실습",
        "컴퓨터비전",
        "캡스톤디자인",
    ]
