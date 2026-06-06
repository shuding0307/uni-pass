import os

from app.services.parser import parse_graduation_requirements
from app.utils.department import normalize_department_name


def test_normalize_department_name_strips_college_prefix():
    assert normalize_department_name("IT대학 컴퓨터공학과") == "컴퓨터공학과"
    assert normalize_department_name("문화예술·공과대학 에너지자원·산업공학부") == "에너지자원·산업공학부"


def test_parse_graduation_requirements_accepts_it_college_department_name():
    pdf_path = os.path.join("data", "raw_requirements", "이수학점표_2025학년도.pdf")

    result = parse_graduation_requirements(pdf_path, target_dept="IT대학 컴퓨터공학과")

    assert result is not None
    assert result["department"] == "컴퓨터공학과"
    assert result["total_credits"] > 0
