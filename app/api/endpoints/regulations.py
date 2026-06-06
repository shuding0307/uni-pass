from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db import Regulation
from app.schemas.regulation import RegulationCreate, RegulationResponse

router = APIRouter(prefix="/api/regulations", tags=["Regulations (RAG 데이터)"])


@router.post("", response_model=RegulationResponse, status_code=201)
def create_regulation(body: RegulationCreate, db: Session = Depends(get_db)):
    """학칙·규정 수동 등록. content_vector는 DB가 자동 생성한다."""
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


@router.get("", response_model=List[RegulationResponse])
def list_regulations(
    major: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """규정 목록 조회. major 파라미터로 학과 필터링 가능."""
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
