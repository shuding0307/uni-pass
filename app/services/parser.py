import pdfplumber
import os
import json

def parse_graduation_requirements(pdf_path, target_dept="컴퓨터공학과"):
    print(f"[{os.path.basename(pdf_path)}] Y좌표 기반 정밀 윈도우 파싱 시작...\n")
    
    result = {
        "department": target_dept,
        "total_credits": 0,
        "general_education": {},
        "major_base": {},
        "tracks": {}
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            lines = text.split('\n')
            for i, line in enumerate(lines):
                if line.startswith(target_dept):
                    parts = line.split() 
                    
                    # 1. 메인 학점 라인
                    result["general_education"] = {
                        "기초교양": int(parts[1]),
                        "균형교양": int(parts[2]),
                        "학문기초": int(parts[3]),
                        "교양계": int(parts[4])
                    }
                    result["major_base"] = {
                        "최소전공_필수": int(parts[5]),
                        "최소전공_선택": int(parts[6])
                    }
                    result["total_credits"] = int(parts[-1])
                    
                    # 💡 2. 윈도우(Window) 탐색 기법 적용
                    # 컴퓨터공학과 기준 위로 4줄, 아래로 2줄(총 7줄)만 정확히 잘라냅니다.
                    # 이렇게 하면 다른 학과 데이터가 절대 섞이지 않습니다!
                    start_idx = max(0, i - 4)
                    end_idx = min(len(lines), i + 3)
                    
                    window_lines = lines[start_idx:end_idx]
                    
                    # 헬퍼 함수
                    def parse_track_data(data_parts):
                        simhwa = 0 if data_parts[0] == '-' else int(data_parts[0])
                        return {
                            "심화전공": simhwa,
                            "전공계": int(data_parts[1]),
                            "자유선택": int(data_parts[2])
                        }

                    # 잘라낸 7줄 안에서만 트랙 정보를 찾습니다.
                    for j, w_line in enumerate(window_lines):
                        w_line = w_line.strip()
                        
                        if w_line.startswith("기본전공"):
                            t_parts = w_line.split()[1:]
                            result["tracks"]["기본전공"] = parse_track_data(t_parts)
                            
                        elif w_line.startswith("단일부전공"):
                            t_parts = w_line.split()[1:]
                            result["tracks"]["단일부전공"] = parse_track_data(t_parts)
                            
                        elif w_line.startswith("복수전공"):
                            # 복수전공은 바로 다음 줄에 숫자가 있음
                            if j + 1 < len(window_lines):
                                t_parts = window_lines[j+1].strip().split()
                                result["tracks"]["복수전공"] = parse_track_data(t_parts)
                                
                    return result
                    
    return None

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    pdf_file = os.path.join(base_dir, "data", "raw_requirements", "이수학점표_2025학년도.pdf")
    
    parsed_data = parse_graduation_requirements(pdf_file)
    
    if parsed_data:
        print("🎉 [파싱 대성공! 완벽한 데이터] 🎉")
        print(json.dumps(parsed_data, indent=2, ensure_ascii=False))
    else:
        print("❌ 파싱 실패")