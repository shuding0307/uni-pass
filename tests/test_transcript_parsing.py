import os
import pandas as pd
from app.utils.transcript_parsing import extract_transcript_tokens

def test_extract_transcript_tokens():
    # 데이터 경로 설정
    test_pdf_path = "data/성적표파일"
    
    # 파일 존재 여부 확인
    assert os.path.exists(test_pdf_path), f"테스트용 PDF 파일이 없습니다: {test_pdf_path}"
    
    # 함수 실행
    student_info, basic_credits, courses_df = extract_transcript_tokens(test_pdf_path)
    
    # 1. 학생 정보 검증
    assert isinstance(student_info, dict)
    assert "학번" in student_info
    assert "소속" in student_info
    assert "총취득학점" in student_info
    
    # 결과 출력 (pytest -s 옵션으로 확인 가능)
    print("\n===== 학생 기본 정보 =====")
    for k, v in student_info.items():
        print(f"{k}: {v}")
        
    # 2. 기본 이수 학점 검증
    assert isinstance(basic_credits, dict)
    print("\n===== 기본 이수 학점 =====")
    for k, v in basic_credits.items():
        print(f"{k}: {v}학점")
        
    # 3. 과목 데이터 검증
    assert isinstance(courses_df, pd.DataFrame)
    assert not courses_df.empty, "추출된 과목이 없습니다."
    
    required_columns = ["과목코드", "교과목명", "학점", "성적"]
    for col in required_columns:
        assert col in courses_df.columns
        
    print("\n===== 이수 과목 목록 (일부) =====")
    print(courses_df.head())
    print(f"총 {len(courses_df)}개의 과목이 추출되었습니다.")

if __name__ == "__main__":
    # 직접 실행 시에도 결과 확인 가능하도록
    test_extract_transcript_tokens()
