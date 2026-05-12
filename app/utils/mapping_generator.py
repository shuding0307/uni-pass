import pandas as pd
import os

from building_converter import get_full_name

# 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_PATH = os.path.join(BASE_DIR, 'data', 'parsed_schedule.csv')
MAPPING_OUT_PATH = os.path.join(BASE_DIR, 'data', 'building_mapping.csv')

def create_mapping_file():
    # 1. 파싱된 데이터 불러오기
    df = pd.read_csv(INPUT_PATH)
    
    # 2. 중복 없는 건물 줄임말 추출
    unique_buildings = df['건물'].unique()
    
    mapping_data = []
    for short in unique_buildings:
        if short == "온라인/장소없음": continue
        
        full = get_full_name(short)
        # 카카오맵 API 검색을 위한 최적의 검색어 조합
        search_query = f"강원대학교 {full}"
        
        mapping_data.append({
            '줄임말': short,
            '풀네임': full,
            '카카오검색어': search_query
        })
    
    # 3. 매핑 데이터 저장
    mapping_df = pd.DataFrame(mapping_data)
    mapping_df.to_csv(MAPPING_OUT_PATH, index=False, encoding='utf-8-sig')
    print(f"매핑 파일 생성 완료: {MAPPING_OUT_PATH}")

create_mapping_file()