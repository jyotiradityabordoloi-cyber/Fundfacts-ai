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
    monkeypatch.setattr(gemini_client, "_resolved_model", None)
    monkeypatch.setattr(gemini_client, "_discovered", [])  # no network: no alternative models unless a test says so
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


# ------------------------------------------------------------------ model retirement (404) -> discovery
from fundfacts.llm import gemini_client as gc  # noqa: E402


def test_pick_model_prefers_stable_general_flash():
    models = [
        {"name": "models/gemini-2.0-flash-lite", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3-flash-preview", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-2.5-flash-image", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
    ]
    assert gc.pick_model(models) == "gemini-3-flash"
    assert gc.pick_model([{"name": "models/gemini-flash-latest", "supportedGenerationMethods": ["generateContent"]}] + models) == "gemini-flash-latest"
    assert gc.pick_model([models[-1]]) is None


def test_retired_model_switches_to_discovered_one(llm, monkeypatch):
    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    monkeypatch.setattr(llm, "gemini_model", "gemini-2.5-flash")
    monkeypatch.setattr(gc, "_discovered", None)
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url)
        if "gemini-2.5-flash" in url:
            return FakeResp(404, {"error": {"message": "This model is no longer available to new users."}})
        return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": '{"answer": "ok", "chunk_id": "x"}'}]}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp(200, {"models": [
        {"name": "models/gemini-3-flash", "supportedGenerationMethods": ["generateContent"]}]}))
    assert gc.generate("s", "u") == '{"answer": "ok", "chunk_id": "x"}'
    assert gc.active_model() == "gemini-3-flash" and calls[-1].endswith("gemini-3-flash:generateContent")
    gc.generate("s", "u")  # second call goes straight to the remembered model
    assert calls[-1].endswith("gemini-3-flash:generateContent") and len(calls) == 3


def test_retired_model_with_nothing_to_switch_to_is_reported(llm, monkeypatch):
    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    monkeypatch.setattr(gc, "_resolved_model", None)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(404, {"error": {"message": "gone"}}))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp(200, {"models": []}))
    with pytest.raises(LLMUnavailable, match="no other Flash model"):
        gc.generate("s", "u")


def test_overloaded_model_fails_over_to_another_free_model(llm, monkeypatch):
    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    monkeypatch.setattr(llm, "gemini_model", "gemini-flash-latest")
    monkeypatch.setattr(gc, "_discovered", None)
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append(url.split("/models/")[1].split(":")[0])
        assert timeout <= gc.ATTEMPT_TIMEOUT_S
        if "lite" not in url:
            return FakeResp(503, {"error": {"message": "This model is currently experiencing high demand."}})
        return FakeResp(200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp(200, {"models": [
        {"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
        for n in ["gemini-flash-latest", "gemini-3-flash", "gemini-flash-lite-latest"]]}))
    assert gc.generate("s", "u") == "ok"
    assert calls == ["gemini-flash-latest", "gemini-flash-lite-latest"]  # busy model -> fast Lite model
    assert gc.active_model() == "gemini-flash-lite-latest"


def test_all_models_busy_reports_unavailable(llm, monkeypatch):
    monkeypatch.setattr(llm, "gemini_api_key", "g-key")
    monkeypatch.setattr(gc, "_discovered", ["gemini-flash-lite-latest", "gemini-3-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"])
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(503, {"error": {"message": "busy"}}))
    with pytest.raises(LLMUnavailable) as err:
        gc.generate("s", "u")
    msg = str(err.value)
    assert msg.count("HTTP 503") == 3 and "gemini-2.0-flash:" not in msg  # 4th model never tried


def test_rank_models_puts_fast_lite_first():
    models = [{"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]}
              for n in ["gemini-flash-lite-latest", "gemini-3-flash", "gemini-2.5-flash-image", "gemini-flash-latest"]]
    assert gc.rank_models(models) == ["gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3-flash"]
