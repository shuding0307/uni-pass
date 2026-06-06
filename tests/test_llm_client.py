from app.services.llm_client import LLMClient


def test_llm_client_uses_gemini_when_openai_key_is_missing(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": '{"selected":[{"index":0,"rationale":"좋은 구성입니다."}]}'}
                            ]
                        }
                    }
                ]
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.services.llm_client.requests.post", fake_post)

    client = LLMClient(api_key="", gemini_api_key="gemini-key", gemini_model="gemini-test")

    assert client.enabled is True
    assert client.provider == "gemini"
    assert client.complete_json("system", '{"hello":"world"}') == {
        "selected": [{"index": 0, "rationale": "좋은 구성입니다."}]
    }
    assert captured["url"].endswith("/models/gemini-test:generateContent")
    assert captured["headers"]["x-goog-api-key"] == "gemini-key"
    assert captured["json"]["generationConfig"]["response_mime_type"] == "application/json"


def test_llm_client_is_disabled_without_openai_or_gemini_key():
    client = LLMClient(api_key="", gemini_api_key="")

    assert client.enabled is False
    assert client.provider is None
    assert client.complete_json("system", "user") is None
