import pandas as pd
import requests
import os
import time

# 1. 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_PATH = os.path.join(BASE_DIR, 'data', 'building_mapping.csv')

OUTPUT_PATH = os.path.join(BASE_DIR, 'data', 'building_coords.csv')

KAKAO_API_KEY = "708d4da984d130fa05debdbce8388e3b"

def get_coords_from_kakao(query):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()
        
        # [디버깅용 출력] 서버에서 어떤 응답을 주는지 직접 확인합니다.
        if "errorType" in data:
            print(f"❌ API 에러 발생: {data['errorType']} - {data['message']}")
            return None, None
            
        if data.get('documents'):
            return data['documents'][0]['x'], data['documents'][0]['y']
        else:
            # 검색 결과가 아예 없는 경우
            print(f"❓ 검색 결과 없음: {query}")
            
    except Exception as e:
        print(f"⚠️ 코드 실행 에러: {e}")
        
    return None, None

def run_coordinate_fetcher():
    # 1. mapping_generator.py가 만든 파일을 읽어옵니다.
    if not os.path.exists(INPUT_PATH):
        print(f"에러: {INPUT_PATH} 파일이 없습니다. mapping_generator.py를 먼저 실행하세요.")
        return

    mapping_df = pd.read_csv(INPUT_PATH)
    print(f"총 {len(mapping_df)}개의 건물 좌표 수집을 시작합니다...")

    # 2. [사용처] 각 행을 돌면서 카카오 API 함수를 호출합니다.
    # '카카오검색어' 컬럼의 값을 함수에 넣고, 결과(x, y)를 새로운 컬럼에 저장합니다.
    x_coords = []
    y_coords = []

    for index, row in mapping_df.iterrows():
        query = row['카카오검색어']
        print(f"[{index+1}/{len(mapping_df)}] 검색 중: {query}")
        
        x, y = get_coords_from_kakao(query)
        x_coords.append(x)
        y_coords.append(y)
        
        # API 과부하 방지를 위한 미세한 대기 시간 (0.1초)
        time.sleep(0.1)

    # 3. 기존 데이터프레임에 좌표 컬럼 추가
    mapping_df['X좌표'] = x_coords
    mapping_df['Y좌표'] = y_coords

    # 4. 최종 파일 저장 (building_coords.csv)
    # 이제 이 파일 하나에 줄임말, 풀네임, 검색어, X, Y가 모두 들어있습니다!
    mapping_df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
    print(f"최종 파일 저장됨: {OUTPUT_PATH}")

run_coordinate_fetcher()