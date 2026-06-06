from sqlalchemy.exc import SQLAlchemyError

from app.services.rag_service import RagService


class FailingSession:
    def execute(self, *_args, **_kwargs):
        raise SQLAlchemyError("database unavailable")

    def rollback(self):
        self.rolled_back = True


def test_rag_search_returns_empty_list_on_database_error():
    db = FailingSession()

    results = RagService(db).search(["꿈-설계", "기초교양"], major="IT대학 컴퓨터공학과")

    assert results == []
    assert db.rolled_back is True
