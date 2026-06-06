from fastapi import APIRouter, HTTPException
from app.models.graduation import GraduationRequirement
from app.services.parser import parse_graduation_requirements
from app.utils.department import normalize_department_name
import os

# 라우터 생성
router = APIRouter(
    prefix="/api/graduation",
    tags=["Graduation Requirements"]
)

@router.get("/requirements", response_model=GraduationRequirement)
async def get_graduation_requirements(year: str = "2025", department: str = "컴퓨터공학과"):
    """
    특정 연도와 학과의 졸업 이수 요건을 조회합니다.
    - 해당 연도의 PDF가 없으면 최신(2025년도) 데이터를 기본으로 반환합니다.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    
    # 1. 요청받은 연도의 PDF 파일 경로 확인
    pdf_file = os.path.join(base_dir, "data", "raw_requirements", f"이수학점표_{year}학년도.pdf")
    
    # 2. 파일이 없으면 2025학년도 파일로 Fallback (대체)
    if not os.path.exists(pdf_file):
        print(f"[{year}학년도] 파일이 없어 최신 2025학년도 데이터로 대체합니다.")
        pdf_file = os.path.join(base_dir, "data", "raw_requirements", "이수학점표_2025학년도.pdf")
        
        # 2025년도 파일마저 없다면 에러 처리
        if not os.path.exists(pdf_file):
             raise HTTPException(status_code=404, detail="서버에 이수학점표 PDF 파일이 존재하지 않습니다.")

    normalized_department = normalize_department_name(department, default="컴퓨터공학과")

    # 3. 파싱 로직 실행
    parsed_data = parse_graduation_requirements(pdf_file, target_dept=normalized_department)
    
    # 4. 결과가 없으면 에러, 있으면 Pydantic 모델(response_model)에 맞춰 자동 반환
    if not parsed_data:
        raise HTTPException(status_code=404, detail=f"'{normalized_department}'의 데이터를 찾거나 파싱할 수 없습니다.")
        
    return parsed_data
