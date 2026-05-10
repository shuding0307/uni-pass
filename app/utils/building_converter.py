import re

def get_full_name(short_name):
    # 1. 예외 및 고유 명칭 처리 (온라인 등)
    if short_name == "온라인/장소없음" or not short_name:
        return short_name

    # 2. 사용자 정의 패턴 매핑 (우선순위 고려)
    # 의생명A호처럼 긴 패턴을 먼저 체크해야 함
    mapping = {
        '의생명A호관': '의생명과학관',
        '의생명B호관': '의생명과학관',
        '인': '인문대학',
        '자': '자연과학대학',
        '공': '공과대학',
        '경영': '경영대학',
        '농': '농업생명대학',
        '산': '산림환경대학',
        '예술': '문화예술대학',
        '의학': '의과대학'
    }

    # 패턴 매칭 및 변환
    for key, full in mapping.items():
        if short_name.startswith(key):
            # 예: '공1호관' -> '공과대학' + '1호관'
            suffix = short_name[len(key):]
            # 호관 앞에 공백을 넣어 검색 정확도 향상 (예: 공과대학 1호관)
            return f"{full} {suffix}".strip()

    # 3. 매칭되는 패턴이 없으면 고유 명칭으로 반환 (60주년기념관 등)
    return short_name