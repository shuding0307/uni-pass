"""강의 시간(요일+교시) 문자열 파싱과 시간 충돌 검사.

강원대 개설강좌의 시간 문자열 형식 (강의실 컬럼에 혼재):
    "월A5,목A5(60주년기념관 208)"   # 월·목 A5교시, 60주년기념관 208호
    "수6,7,8(60주년기념관 504)"      # 수 6·7·8교시 (요일 생략 시 직전 요일 상속)
    "화5,수5,6(자1호관 004)"         # 중간에 요일 변경
    "목11"                           # 건물 정보 없는 경우

교시 코드는 두 체계가 공존한다:
    - 숫자형 1~14
    - 알파벳형 A1~A7
서로 다른 체계이므로 '6'과 'A6'은 다른 시간이다. → 교시는 불투명한 문자열 토큰으로 비교한다.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

DAYS = "월화수목금토일"
# "월A5", "6", "A3", "11" 등에서 (요일?, 교시코드) 추출
_TOKEN_RE = re.compile(rf"([{DAYS}])?\s*([A-Z]?\d+)")
# 괄호 안 건물/호실: "60주년기념관 208", "율곡관(기숙사)식당동 102" 포함.
# 중첩 괄호 처리는 _extract_location()에서 직접 스캔.
_BUILDING_RE = re.compile(r"\(([^)]*)\)")


@dataclass(frozen=True)
class TimeSlot:
    day: str       # 요일 한 글자 (월~일)
    period: str    # 교시 코드 토큰 ("5", "A5", "11" ...)

    def __str__(self) -> str:
        return f"{self.day}{self.period}"


def _extract_location(schedule: str) -> Optional[str]:
    """시간 문자열에서 첫 번째 위치 정보(괄호 내용)를 반환한다.

    중첩 괄호 허용: "율곡관(기숙사)식당동 102" → "율곡관(기숙사)식당동 102"
    다중 블록의 첫 번째만: "화1(공1호관 208),수1(미래관 301)" → "공1호관 208"
    """
    if not schedule:
        return None
    start = schedule.find("(")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(schedule[start:], start):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return schedule[start + 1 : i].strip() or None
    return None


def parse_building(schedule: str) -> Optional[str]:
    """시간 문자열 괄호 안에서 건물명만 추출. 없으면 None.

    "60주년기념관 208"        -> "60주년기념관"
    "율곡관(기숙사)식당동 102" -> "율곡관(기숙사)식당동"
    """
    inside = _extract_location(schedule)
    if not inside:
        return None
    # 마지막 공백 이후 토큰이 호실(숫자/알파숫자). 그 앞이 건물명.
    parts = inside.rsplit(None, 1)
    if len(parts) == 1:
        return parts[0]  # 공백 없음 → 전체가 건물명
    # 마지막 토큰이 호실처럼 보이면(영숫자) 앞부분만 건물명
    if re.match(r"^[A-Za-z0-9]+$", parts[1]):
        return parts[0]
    return inside


def parse_room(schedule: str) -> Optional[str]:
    """시간 문자열 괄호 안에서 호실만 추출. 없으면 None.

    "60주년기념관 208"        -> "208"
    "율곡관(기숙사)식당동 102" -> "102"
    "백령스포츠센터 B003"      -> "B003"
    """
    inside = _extract_location(schedule)
    if not inside:
        return None
    parts = inside.rsplit(None, 1)
    if len(parts) < 2:
        return None
    if re.match(r"^[A-Za-z0-9]+$", parts[1]):
        return parts[1]
    return None


def parse_schedule(schedule: Optional[str]) -> List[TimeSlot]:
    """시간 문자열을 TimeSlot 목록으로 파싱한다.

    파싱 불가/빈 값이면 빈 리스트를 반환한다. 호출 측은 빈 리스트(=시간 미상)를
    충돌 검사에서 어떻게 다룰지(보수적으로 충돌 간주 등) 결정할 수 있다.
    """
    if not schedule:
        return []

    # 건물/호실 괄호 부분 제거 → 시간 토큰만 남긴다.
    # 중첩 괄호도 처리: 첫 '(' 이후 depth==0이 되는 ')' 까지를 통째로 제거.
    def _strip_parens(s: str) -> str:
        out, depth = [], 0
        for ch in s:
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth > 0:
                    depth -= 1
                continue
            elif depth == 0:
                out.append(ch)
        return "".join(out)

    time_part = _strip_parens(schedule)

    slots: List[TimeSlot] = []
    last_day: Optional[str] = None
    for raw in time_part.split(","):
        raw = raw.strip()
        if not raw:
            continue
        m = _TOKEN_RE.search(raw)
        if not m:
            continue
        day, period = m.group(1), m.group(2)
        if day:
            last_day = day
        if last_day is None:
            # 요일을 한 번도 못 만난 토큰은 건너뛴다.
            continue
        slots.append(TimeSlot(day=last_day, period=period))
    return slots


def has_conflict(a: List[TimeSlot], b: List[TimeSlot]) -> bool:
    """두 슬롯 목록이 같은 (요일, 교시)를 공유하면 True."""
    set_a = {(s.day, s.period) for s in a}
    return any((s.day, s.period) in set_a for s in b)


def is_early_morning(slots: List[TimeSlot]) -> bool:
    """1교시(이른 아침) 수업 포함 여부. (선호도 점수용)"""
    return any(s.period == "1" for s in slots)


def occupied_keys(slots: List[TimeSlot]) -> set[Tuple[str, str]]:
    """(요일, 교시) 점유 집합. 시간표 전체의 충돌 누적 검사에 사용."""
    return {(s.day, s.period) for s in slots}
