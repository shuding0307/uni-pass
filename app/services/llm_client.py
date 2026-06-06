import json
from typing import Optional
from app.core.config import settings


class LLMClient:
    """OpenAI Chat Completions 얇은 래퍼.

    - API 키가 없으면 enabled=False 가 되어 상위 서비스가 결정론적 폴백을 타도록 합니다.
    - complete_json()은 JSON 응답을 강제하고 dict로 파싱해 반환합니다. 실패 시 None.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            # 지연 임포트: openai 미설치/키 없음 환경에서도 모듈 임포트는 가능하게.
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def complete_json(self, system: str, user: str) -> Optional[dict]:
        """system/user 프롬프트로 JSON 응답을 받아 dict로 반환. 오류 시 None."""
        if not self.enabled:
            return None
        try:
            resp = self._get_client().chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
            )
            content = resp.choices[0].message.content
            return json.loads(content) if content else None
        except Exception:
            # 네트워크/쿼터/파싱 오류 등은 모두 폴백 신호로 처리.
            return None
