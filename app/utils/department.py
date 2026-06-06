def normalize_department_name(department: str | None, default: str | None = None) -> str | None:
    """학적/성적표에서 온 소속 문자열을 졸업요건 PDF의 학과명으로 정규화합니다."""
    if not department:
        return default

    text = str(department).strip()
    if not text:
        return default

    tokens = text.split()
    for token in reversed(tokens):
        if token.endswith(("학과", "학부", "전공")):
            return token

    return text
