from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db import Regulation
from app.schemas.regulation import RegulationCreate, RegulationResponse
from app.services.rag_service import RagService

router = APIRouter(prefix="/api/regulations", tags=["Regulations (RAG 데이터)"])


@router.post("", response_model=RegulationResponse, status_code=201)
def create_regulation(body: RegulationCreate, db: Session = Depends(get_db)):
    """학칙·규정 수동 등록. content_vector는 DB가 자동 생성한다."""
    try:
        reg = Regulation(
            title=body.title,
            content=body.content,
            major=body.major,
            source_tag=body.source_tag,
            effective_date=body.effective_date,
            is_active=True,
        )
        db.add(reg)
        db.commit()
        db.refresh(reg)
        return RegulationResponse(
            id=str(reg.id),
            title=reg.title,
            content=reg.content,
            major=reg.major,
            source_tag=reg.source_tag,
            effective_date=reg.effective_date,
            is_active=reg.is_active,
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"학칙 데이터베이스 오류: {str(e)}")


@router.get("", response_model=List[RegulationResponse])
def list_regulations(
    major: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """규정 목록 조회. major 파라미터로 학과 필터링 가능."""
    try:
        query = db.query(Regulation).filter(Regulation.is_active == True)
        if major:
            query = query.filter(Regulation.major == major)
        regs = query.order_by(Regulation.effective_date.desc()).all()
        return [
            RegulationResponse(
                id=str(r.id),
                title=r.title,
                content=r.content,
                major=r.major,
                source_tag=r.source_tag,
                effective_date=r.effective_date,
                is_active=r.is_active,
            )
            for r in regs
        ]
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=f"학칙 데이터베이스 오류: {str(e)}")


@router.get("/search")
def search_regulations(
    q: str,
    major: Optional[str] = None,
    top_k: int = 4,
    db: Session = Depends(get_db),
):
    """RAG용 학칙 전문검색. 오류 시 500 대신 빈 결과를 반환합니다."""
    if not q.strip():
        return {"query": q, "major": major, "results": []}

    terms = [part for part in re_split_query(q) if part]
    results = RagService(db).search(terms, major=major, top_k=max(1, min(top_k, 10)))
    return {"query": q, "major": major, "results": results}


def re_split_query(query: str) -> List[str]:
    return [term.strip() for term in query.replace(",", " ").split()]
