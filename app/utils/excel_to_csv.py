import pandas as pd
import os

# 1. 파일 경로 설정
# 현재 프로젝트 루트 기준의 data 폴더 내 파일을 가리킵니다.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE_NAME = 'courses_list_2026_1.xlsx'
INPUT_PATH = os.path.join(BASE_DIR, 'data', FILE_NAME)

# 저장할 CSV 파일 경로 (바탕화면 대신 프로젝트 data 폴더 권장)
OUTPUT_NAME = 'output.csv'
OUTPUT_PATH = os.path.join(BASE_DIR, 'data', OUTPUT_NAME)

def convert_excel_to_csv():
    # 파일이 존재하는지 확인
    if not os.path.exists(INPUT_PATH):
        print(f"❌ 파일을 찾을 수 없습니다: {INPUT_PATH}")
        print("data 폴더에 엑셀 파일이 있는지 확인해 주세요.")
        return

    try:
        print(f"🔄 파일 읽는 중: {FILE_NAME}...")
        
        # 2. 엑셀 파일 읽기 (pandas 사용)
        # header=0 은 첫 번째 줄을 컬럼명으로 사용한다는 뜻입니다.
        df = pd.read_excel(INPUT_PATH)

        # 3. 원하는 열(Column) 선택
        """
        0 : 구분 (전공, 교양 등)
        1 : 과목코드
        2 : 분반
        3 : 과목명
        4 : 시수
        5 : 부문 (인문학, 자연, 사회, 예술 등)
        6 : 대상학과 및 학년
        7 : 대학 (학부)
        8 : 학과
        9 : 교수
        10 : 강의실
        11 : 원격 수업
        """
        # pandas는 0부터 시작하므로, 요청하신 번호에서 1을 뺍니다.
        # columns = [1, 2, 3, 4, 6, 7, 8, 9, 10, 11] -> [0, 1, 2, 3, 5, 6, 7, 8, 9, 10]
        selected_indices = [1,2, 3, 4, 5, 6, 13]
        
        # 실제 존재하는 컬럼 개수 확인 후 선택
        df_selected = df.iloc[:, selected_indices]

        # 4. CSV로 저장 (한글 깨짐 방지 utf-8-sig)
        df_selected.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        
        print(f"✅ 변환 완료!")
        print(f"📍 저장 위치: {OUTPUT_PATH}")
        print("-" * 30)
        print(df_selected.head()) # 상위 데이터 미리보기

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    convert_excel_to_csv()
