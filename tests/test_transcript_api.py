from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_parse_transcript_accepts_pdf_upload(monkeypatch):
    def fake_extract_transcript_tokens(file_path):
        import pandas as pd

        return (
            {"학번": "202210279", "소속": "IT대학 컴퓨터공학과", "총취득학점": "103"},
            {"기초": "17", "전필": "33"},
            pd.DataFrame(
                [
                    {
                        "과목코드": "4471057",
                        "교과목명": "인공지능수학",
                        "학점": 3,
                        "성적": "B+",
                        "이수구분": "전공필수",
                    }
                ]
            ),
        )

    monkeypatch.setattr(
        "app.api.endpoints.validator.extract_transcript_tokens",
        fake_extract_transcript_tokens,
    )

    response = client.post(
        "/api/transcript/parse",
        files={"file": ("transcript.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "student_id": "202210279",
        "department": "IT대학 컴퓨터공학과",
        "admission_year": 2022,
        "total_earned_credits": 103,
        "basic_credits": {"기초": "17", "전필": "33"},
        "taken_courses": [
            {
                "course_code": "4471057",
                "name": "인공지능수학",
                "credits": 3,
                "area_type": "전공필수",
                "grade": "B+",
                "sub_area": None,
            }
        ],
    }


def test_parse_transcript_rejects_non_pdf_upload():
    response = client.post(
        "/api/transcript/parse",
        files={"file": ("transcript.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "PDF 파일만 업로드 가능합니다."
