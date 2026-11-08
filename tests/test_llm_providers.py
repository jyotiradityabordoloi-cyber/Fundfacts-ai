"""LLM provider selection and the Gemini client (no network: httpx is faked)."""
import httpx
import pytest

from fundfacts.config import settings
from fundfacts.llm import gemini_client, router
from fundfacts.llm.base import LLMUnavailable


@pytest.fixture
def llm(monkeypatch):
    for k, v in {"provider": "auto", "gemini_api_key": "", "anthropic_api_key": ""}.items():
        monkeypatch.setattr(settings.llm, k, v)
    return settings.llm


@pytest.mark.parametrize("provider,gem,ant,expected", [
    ("auto", "", "", None),                 # free mode: no key at all
    ("auto", "g-key", "", "gemini"),
    ("auto", "", "a-key", "anthropic"),
    ("auto", "g-key", "a-key", "gemini"),   # the free provider wins in auto
    ("anthropic", "g-key", "a-key", "anthropic"),
    ("gemini", "", "a-key", None),          # asked for Gemini but no Gemini key
    ("none", "g-key", "a-key", None),
])
def test_active_provider(llm, monkeypatch, provider, gem, ant, expected):
    monkeypatch.setattr(llm, "provider", provider)
    monkeypatch.setattr(llm, "gemini_api_key", gem)
    monkeypatch.setattr(llm, "anthropic_api_key", ant)
    assert llm.active == expected and router.provider() == expected and router.enabled() == (expected is not None)


def test_router_without_provider_raises(llm):
    with pytest.raises(LLMUnavailable):
        router.generate("s", "u")


class FakeResp:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload
        self.request = httpx.Request("POST", "https://example.com")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=self.request, response=httpx.Response(self.status_code))

    def json(self):
        return self._payload


def test_gemini_request_and_parse(llm, monkeypatch):
    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, headers=headers, body=json)
        return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": '{"answer": "ok", "chunk_id": "x"}'}]}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = router.generate("SYSTEM", "QUESTION")
    assert out == '{"answer": "ok", "chunk_id": "x"}'
    assert sent["headers"]["x-goog-api-key"] == "g-key" and "key=" not in sent["url"]  # key never in the URL
    assert sent["body"]["systemInstruction"]["parts"][0]["text"] == "SYSTEM"
    assert sent["body"]["generationConfig"]["responseMimeType"] == "application/json"


@pytest.mark.parametrize("status,payload", [(429, {}), (200, {"candidates": []}), (200, {"promptFeedback": {"blockReason": "SAFETY"}})])
def test_gemini_quota_or_empty_response_becomes_unavailable(llm, monkeypatch, status, payload):
    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(status, payload))
    with pytest.raises(LLMUnavailable):
        gemini_client.generate("s", "u")


@pytest.mark.skipif(not settings.paths.index_export.exists(), reason="run the ingestion pipeline first")
def test_quota_exhausted_falls_back_to_verified_quote(llm, monkeypatch):
    from fundfacts.query.answer import answer

    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(429, {}))
    a = answer("What is NAV?")
    assert a.type.value == "answer" and "Net Asset Value" in a.text  # still answered, from the source text
