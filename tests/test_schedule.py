from app.services.schedule import (
    parse_schedule,
    parse_building,
    parse_room,
    has_conflict,
    is_early_morning,
    TimeSlot,
)


def test_parse_basic_two_days():
    slots = parse_schedule("월A5,목A5(60주년기념관 208)")
    assert slots == [TimeSlot("월", "A5"), TimeSlot("목", "A5")]


def test_parse_consecutive_periods_inherit_day():
    # "수6,7,8" → 요일 생략 토큰은 직전 요일(수)을 상속
    slots = parse_schedule("수6,7,8(60주년기념관 504)")
    assert slots == [TimeSlot("수", "6"), TimeSlot("수", "7"), TimeSlot("수", "8")]


def test_parse_day_changes_midlist():
    slots = parse_schedule("화5,수5,6(자1호관 004)")
    assert slots == [TimeSlot("화", "5"), TimeSlot("수", "5"), TimeSlot("수", "6")]


def test_parse_no_building():
    assert parse_schedule("목11") == [TimeSlot("목", "11")]


def test_parse_empty_or_none():
    assert parse_schedule(None) == []
    assert parse_schedule("") == []
    assert parse_schedule("강의실 미정") == []


def test_parse_building():
    assert parse_building("월A5,목A5(60주년기념관 208)") == "60주년기념관"
    assert parse_building("화2,3,4(백령스포츠센터 B003)") == "백령스포츠센터"
    assert parse_building("목11") is None


def test_parse_room():
    assert parse_room("수1,2(60주년기념관 402)") == "402"
    assert parse_room("화2,3,4(백령스포츠센터 B003)") == "B003"
    assert parse_room("목11") is None
    assert parse_room(None) is None
    assert parse_room("(한빛관)") is None  # 건물명만, 호실 없음


def test_numeric_and_alpha_periods_are_distinct():
    # 숫자 6과 A6은 다른 교시 → 충돌 아님
    a = parse_schedule("월6")
    b = parse_schedule("월A6")
    assert not has_conflict(a, b)


def test_has_conflict_same_slot():
    a = parse_schedule("월A5,목A5(한빛관 101)")
    b = parse_schedule("목A5,금1(공학6호관 202)")
    assert has_conflict(a, b)


def test_has_conflict_disjoint():
    a = parse_schedule("월1,수1")
    b = parse_schedule("화2,목2")
    assert not has_conflict(a, b)


def test_is_early_morning():
    assert is_early_morning(parse_schedule("월1,수1"))
    assert not is_early_morning(parse_schedule("월3,수3"))
