import os
import json

from app.services.base_parser import BasePdfParser
from app.utils.department import normalize_department_name


class RequirementParser(BasePdfParser):
    """졸업요건 PDF에서 학과별 이수학점 정보를 추출합니다."""

    def parse(self, path: str, target_dept: str = "컴퓨터공학과", **kwargs) -> dict | None:
        target_dept = normalize_department_name(target_dept, default="컴퓨터공학과")
        print(f"[{os.path.basename(path)}] Y좌표 기반 정밀 윈도우 파싱 시작...\n")

        result = {
            "department": target_dept,
            "total_credits": 0,
            "general_education": {},
            "major_base": {},
            "tracks": {},
        }

        with self.open_pdf(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                parsed = _parse_requirement_text(text, target_dept, result)
                if parsed:
                    return parsed

        return None


def parse_graduation_requirements(pdf_path, target_dept="컴퓨터공학과"):
    return RequirementParser().parse(pdf_path, target_dept=target_dept)


def _parse_requirement_text(text: str, target_dept: str, result: dict) -> dict | None:
    target_dept = normalize_department_name(target_dept, default="컴퓨터공학과")
    result["department"] = target_dept

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(target_dept):
            parts = line.split()
            numeric_parts = parts[1:]

            # 이수학점표는 학년도별로 컬럼 수가 다릅니다.
            # 2021 양식: 학과 기초 균형 특화 대교 교양계 전필 전선 총학점
            # 2025 양식: 학과 기초 균형 학문기초 교양계 전필 전선 총학점
            if len(numeric_parts) >= 8:
                basic_ge = int(numeric_parts[0])
                balanced_ge = int(numeric_parts[1])
                specialized_ge = int(numeric_parts[2])
                univ_core_ge = int(numeric_parts[3])
                foundation_ge = 0
                ge_total = int(numeric_parts[4])
                major_required = int(numeric_parts[5])
                major_elective = int(numeric_parts[6])
                total_credits = int(numeric_parts[7])
            else:
                basic_ge = int(numeric_parts[0])
                balanced_ge = int(numeric_parts[1])
                specialized_ge = 0
                univ_core_ge = 0
                foundation_ge = int(numeric_parts[2])
                ge_total = int(numeric_parts[3])
                major_required = int(numeric_parts[4])
                major_elective = int(numeric_parts[5])
                total_credits = int(numeric_parts[-1])

            result["general_education"] = {
                "기초교양": basic_ge,
                "균형교양": balanced_ge,
                "학문기초": foundation_ge,
                "특화교양": specialized_ge,
                "대교": univ_core_ge,
                "교양계": ge_total,
            }
            result["major_base"] = {
                "최소전공_필수": major_required,
                "최소전공_선택": major_elective,
            }
            result["total_credits"] = total_credits

            # 컴퓨터공학과 기준 위로 4줄, 아래로 2줄(총 7줄)만 잘라 트랙 정보를 찾습니다.
            start_idx = max(0, i - 4)
            end_idx = min(len(lines), i + 3)
            window_lines = lines[start_idx:end_idx]

            for j, w_line in enumerate(window_lines):
                w_line = w_line.strip()

                if w_line.startswith("기본전공"):
                    t_parts = w_line.split()[1:]
                    result["tracks"]["기본전공"] = _parse_track_data(t_parts)

                elif w_line.startswith("단일부전공"):
                    t_parts = w_line.split()[1:]
                    result["tracks"]["단일부전공"] = _parse_track_data(t_parts)

                elif w_line.startswith("복수전공") and j + 1 < len(window_lines):
                    t_parts = window_lines[j + 1].strip().split()
                    result["tracks"]["복수전공"] = _parse_track_data(t_parts)

            return result

    return None


def _parse_track_data(data_parts):
    simhwa = 0 if data_parts[0] == "-" else int(data_parts[0])
    return {
        "심화전공": simhwa,
        "전공계": int(data_parts[1]),
        "자유선택": int(data_parts[2]),
    }


if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    pdf_file = os.path.join(base_dir, "data", "raw_requirements", "이수학점표_2025학년도.pdf")
    
    parsed_data = parse_graduation_requirements(pdf_file)
    
    if parsed_data:
        print("🎉 [파싱 대성공! 완벽한 데이터] 🎉")
        print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
    else:
        print("❌ 파싱 실패")
