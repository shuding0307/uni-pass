import os
from dotenv import load_dotenv

# .env 파일을 환경변수로 로드 (이미 주입된 환경변수는 덮어쓰지 않음)
load_dotenv()


class Settings:
    """애플리케이션 설정. 환경변수(.env)에서 값을 읽어옵니다."""

    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    # 기본 모델은 비용/속도 균형을 위해 mini 계열을 사용. .env에서 OPENAI_MODEL로 변경 가능.
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def llm_enabled(self) -> bool:
        """LLM 호출 가능 여부 (API 키 존재 여부)."""
        return bool(self.OPENAI_API_KEY)


settings = Settings()
