import pdfplumber
import pandas as pd
import re

AREA_MAP = {
    "기초": "기초교양",
    "기교": "기초교양",
    "교약": "기초교양",
    "교필": "기초교양",
    "균형": "균형교양",
    "균교": "균형교양",
    "특화": "특화교양",
    "특교": "특화교양",
    "대교": "대학핵심",
    "전필": "전공필수",
    "전선": "전공선택",
    "심화": "심화전공",
    "심전": "심화전공",
    "자선": "자유선택",
    "일선": "일반선택",
    "교직": "교직",
    "학문": "학문기초",
}

AREA_PATTERN = "|".join(sorted(map(re.escape, AREA_MAP), key=len, reverse=True))


def _parse_transcript_text(text):
    student_info = {"학번": None, "이름": None, "department": None, "총취득학점": None}
    basic_credits = {}
    courses = []

    if not text.strip():
        return student_info, basic_credits, pd.DataFrame(courses)

    # 1. 학생 정보 추출 (정규식 기반)
    # 예: "202111109 이주혁 남자 2002.06.02 IT대학 컴퓨터공학과"
    # 소속에는 IT/AI처럼 영문이 섞일 수 있으므로 줄 단위로 넓게 허용합니다.
    student_match = re.search(
        r'(\d{9})\s+([가-힣]{2,4})\s+[남여]\w*\s+[\d\.]+\s+'
        r'([^\n]*?(?:대학|학부)\s+[^\n]*?(?:학과|학부|전공))',
        text
    )
    if student_match:
        student_info["학번"] = student_match.group(1)
        student_info["이름"] = student_match.group(2)
        student_info["department"] = student_match.group(3).strip()
    else:
        # 보조 매칭: 학번 9자리만 찾기
        id_match = re.search(r'20\d{7}', text)
        if id_match: student_info["학번"] = id_match.group(0)
        
        # 보조 매칭: 이름 찾기 (학번 뒤에 나오는 한글 2~4자)
        if student_info["학번"]:
            name_match = re.search(rf'{student_info["학번"]}\s+([가-힣]{{2,4}})', text)
            if name_match: student_info["이름"] = name_match.group(1)

        # 보조 매칭: 학과명만 찾기
        dept_match = re.search(r'[^\n]*?(?:대학|학부)\s+[^\n]*?(?:학과|학부|전공)', text)
        if dept_match: student_info["department"] = dept_match.group(0).strip()

    # 총취득학점 추출
    # 예: "총취득학점 : 130", "취득학점합계 120.0"
    earned_match = re.search(r'(?:총취득학점|취득학점\s*합계)\s*[:\s]*(\d+(?:\.\d)?)', text)
    if earned_match:
        try:
            student_info["총취득학점"] = int(float(earned_match.group(1)))
        except (ValueError, TypeError):
            pass

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

    # 정규식 설명:
    # (영역) (과목코드 7자리) (과목명) [선택적 태그] (학점) (성적) (학기)
    # 예: "교약 1100005 글쓰기와말하기(자연공학) 원 3.0 A+ 2021.1"
    course_pattern = re.compile(
        rf'(?<!\S)({AREA_PATTERN})\s+'
        r'(\d{7})\s+'
        r'(.+?)\s+'
        r'(?:(?:원격|재수강|원|재|MD|M|D|R|N)\s+)*'
        r'(\d+(?:\.\d)?)\s+'
        r'([A-D][+0]|F|P|NP|가|부)\s+'
        r'(\d{4}[\.-](?:[12]|[a-dA-D]))',
        re.MULTILINE
    )

    lines = text.split('\n')
    for line in lines:
        # 한 줄에 과목이 두 개 있을 수도 있으므로 finditer 사용
        matches = course_pattern.finditer(line)
        for match in matches:
            try:
                area_code = match.group(1)
                code = match.group(2)
                name = re.sub(r'\s+', ' ', match.group(3)).strip()
                credits_val = int(float(match.group(4)))
                grade = match.group(5)
                
                # 과목명이 너무 길어지는 오탐 방지 (텍스트 추출 노이즈 제거)
                if len(name) > 40:
                    continue
                
                full_area = AREA_MAP.get(area_code, area_code)
                
                if code not in seen_codes:
                    courses.append({
                        "과목코드": code,
                        "교과목명": name,
                        "학점": credits_val,
                        "성적": grade,
                        "이수구분": full_area,
                        "이수구분원문": area_code,
                    })
                    seen_codes.add(code)
            except (ValueError, TypeError, IndexError):
                continue

    # 총취득학점 보완 (추출 실패 시 합산)
    courses_df = pd.DataFrame(courses)
    if not student_info["총취득학점"] and not courses_df.empty:
        student_info["총취득학점"] = int(courses_df["학점"].sum())

    return student_info, basic_credits, courses_df


def extract_transcript_tokens(file_path):
    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        return _parse_transcript_text(text)
    except Exception as e:
        # 파일 오픈 실패 등 예외 발생 시 빈 데이터 반환하여 상위에서 처리 유도
        student_info = {"학번": None, "이름": None, "department": None, "총취득학점": None}
        basic_credits = {}
        courses = []
        return student_info, basic_credits, pd.DataFrame(courses)
