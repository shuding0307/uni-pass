import pandas as pd
import re
import os

# 1. 경로 설정 (사용자 제공 코드 기준)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FILE_NAME = 'output.csv'
INPUT_PATH = os.path.join(BASE_DIR, 'data', FILE_NAME)

# 저장할 CSV 파일 경로
OUTPUT_NAME = 'parsed_schedule.csv'
OUTPUT_PATH = os.path.join(BASE_DIR, 'data', OUTPUT_NAME)

def parse_knu_schedule(raw_text):
    """
    건물명을 정제하는 파서입니다.
    """
    if pd.isna(raw_text) or not str(raw_text).strip():
        return []
    
    text = str(raw_text).replace(' 또는 ', ', ')
    
    parts = re.split(r'(\((?:[^()]+|\([^()]*\))*\))', text)
    
    parsed_results = []
    temp_times = []
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        if part.startswith('('):
            # 괄호 안의 장소 정보 (양 끝 괄호만 제거)
            location = part[1:-1].strip()
            
            # [수정포인트] 건물명에 괄호가 포함되어 있다면 특수 케이스로 보고 정제하지 않음
            if '(' in location:
                building = location
            else:
                # 일반적인 경우: 마지막 공백 뒤의 호수 제거
                if ' ' in location:
                    building = location.rsplit(' ', 1)[0]
                else:
                    building = re.sub(r'\d+$', '', location).strip()
            
            # 모아둔 시간들 각각을 개별 행으로 생성
            for t in temp_times:
                parsed_results.append({
                    "시간": t,
                    "건물": building
                })
            temp_times = [] 
            
        else:
            # 요일 앞의 콤마를 기준으로 시간 분리
            times = re.split(r',(?=\s*[월화수목금토일])', part)
            for t in times:
                t = t.strip().strip(',')
                if t:
                    temp_times.append(t)
    
    # 괄호가 없는 경우 처리
    for t in temp_times:
        parsed_results.append({
            "시간": t,
            "건물": "온라인/장소없음"
        })
        
    return parsed_results

# 2. 메인 실행 로직
try:
    df = pd.read_csv(INPUT_PATH)
    final_rows = []
    
    for _, row in df.iterrows():
        schedules = parse_knu_schedule(row['강의실'])
        for sch in schedules:
            new_row = row.to_dict()
            new_row['시간'] = sch['시간']
            new_row['건물'] = sch['건물']
            final_rows.append(new_row)
            
    if final_rows:
        final_df = pd.DataFrame(final_rows)
        final_df.to_csv(OUTPUT_PATH, index=False, encoding='utf-8-sig')
        print(f"성공: 데이터가 저장되었습니다.")
    else:
        print("경고: 처리할 데이터가 없습니다.")

except FileNotFoundError:
    print(f"에러: 파일을 찾을 수 없습니다. 경로: {INPUT_PATH}")
except Exception as e:
    print(f"에러 발생: {e}")