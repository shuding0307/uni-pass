import os
import pdfplumber
import pandas as pd
import re

def extract_transcript_tokens(file_path):
    student_info = {"학번": None, "소속": None, "총취득학점": None}
    basic_credits = {}
    courses = []
    
    with pdfplumber.open(file_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

        # 1. 학생 정보 추출 (정규식 기반)
        # 예: "202111109 이주혁 남자 2002.06.02 IT대학 컴퓨터공학과"
        # 소속(학과) 정보를 정확히 뽑기 위해 '대학', '학부' 키워드 활용
        student_match = re.search(
            r'(\d{9})\s+[가-힣]+\s+[남여]\w*\s+[\d\.]+\s+'
            r'([A-Za-z가-힣\·\s]+(?:대학|학부)\s+[A-Za-z가-힣\·\s]+(?:학과|학부|전공))'
            r'\s+[\d\.]+\s+(\d+)\s+(\d+)',
            text
        )
        if student_match:
            student_info["학번"] = student_match.group(1)
            student_info["소속"] = student_match.group(2).strip()
            student_info["총취득학점"] = student_match.group(4)
        else:
            # 보조 매칭: 학번 9자리만 찾기
            id_match = re.search(r'20\d{7}', text)
            if id_match: student_info["학번"] = id_match.group(0)
            # 보조 매칭: 학과명만 찾기
            dept_match = re.search(r'[A-Za-z가-힣\·\s]+대학\s+[A-Za-z가-힣\·\s]+(?:학과|학부|전공)', text)
            if dept_match: student_info["소속"] = dept_match.group(0).strip()
            credits_match = re.search(r'20\d{7}.*?\s+(\d+)\s+(\d+)\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?', text)
            if credits_match: student_info["총취득학점"] = credits_match.group(2)

        # 2. 과목 데이터 추출 및 기본 이수 학점 파싱
        # 기본 이수 학점 표 파싱 (성적표 하단)
        # 예: "기본이수학점 10 12 1 18 9 33 27 20 130"
        basic_match = re.search(r'기본이수학점\s+([\d\s]+)', text)
        if basic_match:
            nums = basic_match.group(1).split()
            cats = ["기초", "균형", "특화", "대교", "전필", "전선", "심화", "교직", "자선"]
            for idx, cat in enumerate(cats):
                if idx < len(nums):
                    basic_credits[cat] = nums[idx]

        seen_codes = set()
        
        # 이수구분 약어 -> 정식 명칭 매핑
        area_map = {
            "기초": "기초교양", "균형": "균형교양", "특화": "특화교양", "대교": "대교", 
            "전필": "전공필수", "전선": "전공선택", "심화": "심화전공", "자선": "자유선택", 
            "일선": "일반선택", "교직": "교직", "학문": "학문기초"
        }

        # 정규식 설명: 
        # (영역) (과목코드 7자리) (과목명) [선택적 태그] (학점) (성적) (학기)
        # 예: "기초 1100005 글쓰기와말하기(자연공학) 3.0 A+ 2021.1"
        course_pattern = re.compile(
            r'(기초|균형|특화|대교|전필|전선|심화|자선|일선|교직|학문)\s+'  # 이수구분
            r'(\d{7})\s+'                                                 # 과목코드
            r'(.+?)\s+'                                                   # 과목명 (비탐욕적 매칭)
            r'(?:[원재MD]\s+)*'                                           # 부가 태그 (원격, 재수강 등)
            r'(\d(?:\.\d)?)\s+'                                           # 학점 (3.0 또는 3)
            r'([A-D][+0]|F|P|NP|가|부)\s+'                                # 성적
            r'(\d{4}[\.-][1-4][a-d]?)',                                    # 학기 (2021.1, 2021-1, 2025-4a)
            re.MULTILINE
        )

        lines = text.split('\n')
        for line in lines:
            # 한 줄에 과목이 두 개 있을 수도 있으므로 finditer 사용
            matches = course_pattern.finditer(line)
            for match in matches:
                area_code = match.group(1)
                code = match.group(2)
                name = match.group(3).strip()
                credits_val = int(float(match.group(4)))
                grade = match.group(5)
                
                # 과목명이 너무 길어지는 오탐 방지 (텍스트 추출 노이즈 제거)
                if len(name) > 30: continue
                
                full_area = area_map.get(area_code, area_code)
                
                if code not in seen_codes:
                    courses.append({
                        "과목코드": code,
                        "교과목명": name,
                        "학점": credits_val,
                        "성적": grade,
                        "이수구분": full_area
                    })
                    seen_codes.add(code)

    return student_info, basic_credits, pd.DataFrame(courses)
