import os
import pandas as pd
import pytest
import glob
from app.utils.transcript_parsing import extract_transcript_tokens, _parse_transcript_text

def get_test_pdf():
    """data 폴더 내의 첫 번째 PDF 파일을 찾아 반환합니다."""
    pdf_files = glob.glob("data/*.pdf")
    if pdf_files:
        return pdf_files[0]
    return None

def test_transcript_parsing_e2e():
    """성적표 파싱의 전체 과정을 검증합니다."""
    test_pdf_path = get_test_pdf()
    
    # 1. 파일 존재 여부 확인
    if not test_pdf_path:
        pytest.skip("테스트용 PDF 파일이 data/ 폴더에 없습니다.")
    
    print(f"\n🔍 테스트 시작: {test_pdf_path}")
    
    # 2. 파서 실행
    student_info, basic_credits, courses_df = extract_transcript_tokens(test_pdf_path)
    
    # 3. 학생 기본 정보 검증
    print("\n[1] 학생 기본 정보 검증")
    assert isinstance(student_info, dict)
    assert student_info["학번"] is not None, "학번 파싱 실패"
    assert student_info["이름"] is not None, "이름 파싱 실패"
    assert len(student_info["학번"]) >= 9, f"학번 형식이 올바르지 않음: {student_info['학번']}"
    assert student_info["총취득학점"] is not None, "총취득학점 파싱 실패"
    print(f"✅ 학번: {student_info['학번']}, 이름: {student_info['이름']}, 총취득학점: {student_info['총취득학점']}")
    
    # 4. 기본 이수 학점 표 검증
    print("\n[2] 기본 이수 학점 표 검증")
    assert isinstance(basic_credits, dict)
    # 기초, 균형, 전필, 전선 중 최소 하나는 있어야 함
    assert any(k in basic_credits for k in ["기초", "균형", "전필", "전선"]), "기본 이수 학점 정보를 찾을 수 없습니다."
    print(f"✅ 발견된 영역: {list(basic_credits.keys())}")
    
    # 5. 과목 데이터프레임 검증 (핵심)
    print("\n[3] 과목 데이터 정밀 검증")
    assert isinstance(courses_df, pd.DataFrame)
    assert not courses_df.empty, "이수 과목이 하나도 추출되지 않았습니다."
    
    # 필수 컬럼 존재 확인
    required_columns = ["과목코드", "교과목명", "학점", "성적"]
    for col in required_columns:
        assert col in courses_df.columns, f"필수 컬럼 누락: {col}"
    
    # 데이터 샘플 확인
    first_course = courses_df.iloc[0]
    assert len(str(first_course["과목코드"])) == 7, f"과목코드 형식이 올바르지 않음 (7자리여야 함): {first_course['과목코드']}"
    assert int(first_course["학점"]) in [1, 2, 3, 4], f"학점 수치가 비정상적임: {first_course['학점']}"
    
    print(f"✅ 총 {len(courses_df)}개 과목 추출 성공")
    print("\n--- 상위 5개 과목 샘플 ---")
    print(courses_df.head())


def test_parse_transcript_text_with_it_college_and_area_aliases():
    text = """
    성적내역
    202111109 이주혁 남자 2002.06.02 IT대학 컴퓨터공학과
    교약 1100005 글쓰기와말하기(자연공학) 원 3.0 A+ 2021.1
    전필 4840003 컴퓨터프로그래밍1 3 B0 2021.2
    전선 4840028 컴퓨터그래픽스 재 3.0 P 2022-1
    총취득학점 : 9
    기본이수학점 10 12 1 18 9 33 27 20 130
    """

    student_info, basic_credits, courses_df = _parse_transcript_text(text)

    assert student_info["학번"] == "202111109"
    assert student_info["이름"] == "이주혁"
    assert student_info["department"] == "IT대학 컴퓨터공학과"
    assert student_info["총취득학점"] == 9
    assert basic_credits["전필"] == "9"

    assert courses_df["이수구분"].tolist() == ["기초교양", "전공필수", "전공선택"]
    assert courses_df["이수구분원문"].tolist() == ["교약", "전필", "전선"]
    assert courses_df["교과목명"].tolist() == [
        "글쓰기와말하기(자연공학)",
        "컴퓨터프로그래밍1",
        "컴퓨터그래픽스",
    ]

if __name__ == "__main__":
    # 직접 실행 시 결과 확인
    try:
        test_transcript_parsing_e2e()
        print("\n✨ 모든 테스트를 통과했습니다!")
    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
