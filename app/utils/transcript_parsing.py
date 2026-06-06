import os
import pdfplumber
import pandas as pd
import re
from app.services.base_parser import BasePdfParser


class TranscriptParser(BasePdfParser):
    """성적표 PDF에서 학생 정보·기본이수학점·과목 내역을 추출합니다."""

    def parse(self, path: str, **kwargs):
        return extract_transcript_tokens(path)


def extract_transcript_tokens(file_path):
    student_info = {
        "학번": None,
        "이름": None,
        "소속": None,
        "department": None,  # develop 호환 키
        "총취득학점": None,
    }
    basic_credits = {}
    courses = []

    try:
        with pdfplumber.open(file_path) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            if not text.strip():
                return student_info, basic_credits, pd.DataFrame(courses)

            # 1. 학생 정보 추출 (정규식 기반)
            # 예: "202111109 이주혁 남자 2002.06.02 IT대학 컴퓨터공학과"
            student_match = re.search(
                r'(\d{9})\s+([가-힣]+)\s+[남여]\w*\s+[\d\.]+\s+'
                r'([A-Za-z가-힣\·\s]+(?:대학|학부)\s+[A-Za-z가-힣\·\s]+(?:학과|학부|전공))'
                r'\s+[\d\.]+\s+(\d+)\s+(\d+)',
                text
            )
            if student_match:
                student_info["학번"] = student_match.group(1)
                student_info["이름"] = student_match.group(2).strip()
                dept = student_match.group(3).strip()
                student_info["소속"] = dept
                student_info["department"] = dept
                student_info["총취득학점"] = student_match.group(5)
            else:
                # 보조 매칭: 학번 9자리
                id_match = re.search(r'20\d{7}', text)
                if id_match:
                    student_info["학번"] = id_match.group(0)

                # 보조 매칭: 학과명 (feat/#31 + develop 패턴 병합)
                dept_match = re.search(
                    r'[A-Za-z가-힣\·\s]+대학\s+[A-Za-z가-힣\·\s]+(?:학과|학부|전공)', text
                )
                if dept_match:
                    dept = dept_match.group(0).strip()
                    student_info["소속"] = dept
                    student_info["department"] = dept

                # 보조 매칭: 총취득학점 (develop 패턴 — 더 넓은 커버리지)
                earned_match = re.search(
                    r'(?:총취득학점|취득학점\s*합계)\s*[:\s]*(\d+(?:\.\d)?)', text
                )
                if earned_match:
                    try:
                        student_info["총취득학점"] = int(float(earned_match.group(1)))
                    except (ValueError, TypeError):
                        pass
                else:
                    credits_match = re.search(
                        r'20\d{7}.*?\s+(\d+)\s+(\d+)\s+\d+(?:\.\d+)?\s+\d+(?:\.\d+)?', text
                    )
                    if credits_match:
                        student_info["총취득학점"] = credits_match.group(2)

            # 2. 기본 이수 학점 표 파싱 (성적표 하단)
            # 예: "기본이수학점 10 12 1 18 9 33 27 20 130"
            basic_match = re.search(r'기본이수학점\s+([\d\s]+)', text)
            if basic_match:
                nums = basic_match.group(1).split()
                cats = ["기초", "균형", "특화", "대교", "전필", "전선", "심화", "교직", "자선"]
                for idx, cat in enumerate(cats):
                    if idx < len(nums):
                        basic_credits[cat] = nums[idx]

            seen_codes = set()

            # 이수구분 약어 → 정식 명칭 매핑
            area_map = {
                "기초": "기초교양", "균형": "균형교양", "특화": "특화교양", "대교": "대교",
                "전필": "전공필수", "전선": "전공선택", "심화": "심화전공", "자선": "자유선택",
                "일선": "일반선택", "교직": "교직", "학문": "학문기초"
            }

            # (영역) (과목코드 7자리) (과목명) [선택적 태그] (학점) (성적) (학기)
            # 예: "기초 1100005 글쓰기와말하기(자연공학) 3.0 A+ 2021.1"
            course_pattern = re.compile(
                r'(기초|균형|특화|대교|전필|전선|심화|자선|일선|교직|학문)\s+'
                r'(\d{7})\s+'
                r'(.+?)\s+'
                r'(?:[원재MD]\s+)*'
                r'(\d(?:\.\d)?)\s+'
                r'([A-D][+0]|F|P|NP|가|부)\s+'
                r'(\d{4}[\.-][1-4][a-d]?)',
                re.MULTILINE
            )

            lines = text.split('\n')
            for line in lines:
                for match in course_pattern.finditer(line):
                    area_code = match.group(1)
                    code = match.group(2)
                    name = match.group(3).strip()
                    credits_val = int(float(match.group(4)))
                    grade = match.group(5)

                    if len(name) > 30:
                        continue

                    full_area = area_map.get(area_code, area_code)

                    if code not in seen_codes:
                        courses.append({
                            "과목코드": code,
                            "교과목명": name,
                            "학점": credits_val,
                            "성적": grade,
                            "이수구분": full_area,
                        })
                        seen_codes.add(code)

    except Exception:
        pass

    return student_info, basic_credits, pd.DataFrame(courses)
