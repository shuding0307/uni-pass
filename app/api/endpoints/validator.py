from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.transcript import StudentTranscript
from app.models.graduation import GraduationRequirement
from app.services.validator import GraduationValidator
from app.services.recommender import RecommenderService
from typing import Dict, Any

router = APIRouter(
    prefix="/api/validator",
    tags=["Validator & Recommender"]
)

@router.post("/analyze")
async def analyze_and_recommend(
    transcript: StudentTranscript,
    requirement: GraduationRequirement,
    db: Session = Depends(get_db)
):
    """
    학생 성적표와 졸업 요건을 입력받아 졸업 사정을 수행하고, 
    부족한 영역에 대해 이번 학기 개설 과목을 추천합니다.
    """
    try:
        # 1. 졸업 사정 (Validator)
        validator = GraduationValidator(requirement, transcript)
        analysis_result = validator.analyze()
        
        # 2. 과목 추천 (Recommender)
        recommender = RecommenderService(db)
        recommendations = recommender.recommend_courses(analysis_result["deficiency_map"])
        
        return {
            "analysis": analysis_result,
            "recommendations": recommendations
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
