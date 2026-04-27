import os
import pdfplumber
import pandas as pd
import re

def extract_transcript_tokens(file_path):
    student_info = {"학번": None, "소속": None, "총취득학점": None}
    basic_credits = {}
    courses = []
    
    with pdfplumber.open(file_path) as pdf:
        all_tokens = []
        full_text = ""
        
        # 1. 텍스트 및 토큰 추출
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
            
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row: continue
                    for cell in row:
                        if cell:
                            # 셀 내부에 줄바꿈(\n)이 있으면 분리해서 리스트에 쭉 이어붙임
                            for part in str(cell).split('\n'):
                                part = part.strip()
                                if part:
                                    all_tokens.append(part)
        
        # 2. 학생 기본 정보 추출
        for i, token in enumerate(all_tokens):
            if re.fullmatch(r'20\d{7}', token) and not student_info["학번"]:
                student_info["학번"] = token
                
                # 학번 근처에서 소속 찾기
                for j in range(1, 15):
                    if i + j < len(all_tokens) and "대학" in all_tokens[i+j]:
                        student_info["소속"] = all_tokens[i+j]
                        break
        
        # 총취득학점 (보통 112 94 255.0 처럼 신청, 취득, 평점 순으로 나열됨)
        credit_match = re.search(r'(\d{2,3})\s+(\d{2,3})\s+\d{2,3}\.\d', full_text)
        if credit_match:
            student_info["총취득학점"] = credit_match.group(2)
            
        # 기본 이수 학점 (텍스트 정규식으로 안전하게 뽑기)
        basic_match = re.search(r'기본이수학점\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', full_text)
        if basic_match:
            cats = ["기초", "균형", "특화", "대교", "전필", "전선"]
            for idx, cat in enumerate(cats):
                basic_credits[cat] = basic_match.group(idx + 1)
            
        # 3. 과목 데이터 추출
        for i, token in enumerate(all_tokens):
            # 7자리 숫자를 과목코드로 인식
            if re.fullmatch(r'\d{7}', token):
                code = token
                name = ""
                credit = ""
                grade = ""
                
                # 패턴 A: 이름 -> 코드 -> 학점 -> 성적 (예: 컴퓨터개론 1400149 3 A+)
                if i + 1 < len(all_tokens) and re.fullmatch(r'[1-3](?:\.0)?', all_tokens[i+1]) and i > 0:
                    name = all_tokens[i-1]
                    credit = all_tokens[i+1]
                    if i + 2 < len(all_tokens): 
                        grade = all_tokens[i+2]
                        
                # 패턴 B: 코드 -> 이름 -> 학점 -> 성적 (예: 1400149 컴퓨터개론 3 A+)
                else:
                    name_cand = all_tokens[i+1] if i + 1 < len(all_tokens) else ""
                    
                    # 학점이 바로 다음에 오는 경우
                    if i + 2 < len(all_tokens) and re.fullmatch(r'[1-3](?:\.0)?', all_tokens[i+2]):
                        name = name_cand
                        credit = all_tokens[i+2]
                        if i + 3 < len(all_tokens): 
                            grade = all_tokens[i+3]
                            
                    # 중간에 '원', '재' 같은 수강구분이 껴있는 경우
                    elif i + 3 < len(all_tokens) and re.fullmatch(r'[1-3](?:\.0)?', all_tokens[i+3]):
                        name = name_cand
                        credit = all_tokens[i+3]
                        if i + 4 < len(all_tokens): 
                            grade = all_tokens[i+4]
                            
                # PDF 인식 오류로 숫자 0이 알파벳 O로 나오는 경우 수정 (예: B0 -> BO)
                grade = grade.replace('O', '0')
                valid_grades = ['A+', 'A0', 'B+', 'B0', 'C+', 'C0', 'D+', 'D0', 'F', '가', '부', 'P', 'NP']
                
                # 정상적인 데이터만 추가하고 중복 걸러내기
                if name and credit and any(vg in grade for vg in valid_grades):
                    if not any(c['과목코드'] == code for c in courses):
                        courses.append({
                            "과목코드": code,
                            "교과목명": name,
                            "학점": credit.replace('.0', ''),
                            "성적": grade
                        })
                        
    return student_info, basic_credits, pd.DataFrame(courses)

current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, 'pdf.pdf')
student_info, basic_credits, courses_df = extract_transcript_tokens(file_path)

print("===== 학생 기본 정보 =====")
for k, v in student_info.items():
    print(f"{k}: {v}")
    
print("\n===== 기본 이수 학점 =====")
for k, v in basic_credits.items():
    print(f"{k}: {v}학점")

print("\n===== 이수 과목 목록 =====")
pd.set_option('display.max_rows', None)
print(courses_df)