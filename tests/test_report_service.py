import uuid
import pytest
from unittest.mock import MagicMock
from sqlalchemy.exc import SQLAlchemyError

from app.services.report_service import ReportService
from app.models.graduation import GraduationRequirement


@pytest.fixture
def requirement():
    return GraduationRequirement(
        department="컴퓨터공학과",
        total_credits=130,
        major_base={"최소전공_필수": 9, "최소전공_선택": 33},
        general_education={"기초교양": 17, "균형교양": 15, "학문기초": 0, "교양계": 32},
        tracks={"기본전공": {"심화전공": 27, "전공계": 69, "자유선택": 29}},
    )


@pytest.fixture
def analysis():
    return {
        "is_graduatable": False,
        "buckets_status": {"전공필수": 6},
        "deficiency_map": {"전공필수": 3},
        "total_valid_credits": 6,
        "simulation_load": {"planned_credits": 0, "message": "적절한 수강 계획입니다."},
    }


@pytest.fixture
def mock_db():
    db = MagicMock()
    # 학생·요건 모두 미존재 → None 반환
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def test_save_result_commits_to_db(mock_db, requirement, analysis):
    service = ReportService(mock_db)
    service.save_result("20230001", 2023, requirement, analysis)
    mock_db.add.assert_called()
    mock_db.commit.assert_called_once()


def test_save_result_returns_none_on_db_error(requirement, analysis):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    db.add.side_effect = SQLAlchemyError("DB error")

    service = ReportService(db)
    result = service.save_result("20230001", 2023, requirement, analysis)

    assert result is None
    db.rollback.assert_called_once()


def test_get_history_returns_formatted_list():
    db = MagicMock()
    mock_record = MagicMock()
    mock_record.id = uuid.uuid4()
    mock_record.analyzed_at = None
    mock_record.result_json = {"is_graduatable": False}
    mock_record.deficiency_map = {"전공필수": 3}

    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_record]

    service = ReportService(db)
    history = service.get_history("20230001")

    assert len(history) == 1
    assert history[0]["is_graduatable"] is False
    assert history[0]["deficiency_map"] == {"전공필수": 3}
    assert "analyzed_at" in history[0]


def test_get_history_returns_empty_for_unknown_student():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    service = ReportService(db)
    history = service.get_history("99999999")

    assert history == []


def test_save_result_creates_student_when_not_exists(mock_db, requirement, analysis):
    service = ReportService(mock_db)
    service.save_result("20230001", 2023, requirement, analysis)

    # add가 최소 2회 호출 (Student + GraduationRequirementDB + AnalysisResult)
    assert mock_db.add.call_count >= 2
