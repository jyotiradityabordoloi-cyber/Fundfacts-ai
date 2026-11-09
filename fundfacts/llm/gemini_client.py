"""Google Gemini (Generative Language API) over httpx.

Free tier: create a key at https://aistudio.google.com/app/apikey (no credit card) and set
GEMINI_API_KEY. Note: on Google's free tier, prompts may be used by Google to improve its
products - FundFacts AI only ever sends the question (after the PII guardrail) and public
document passages.

Model choice: GEMINI_MODEL (default "gemini-flash-latest", Google's alias for the current Flash
model). Google retires model names over time; if the configured model answers 404, the client
asks the API which models this key may use, picks the best Flash model and remembers it.
"""
from __future__ import annotations

import re

import httpx

from fundfacts.config import settings
from fundfacts.llm.base import LLMUnavailable

BASE = "https://generativelanguage.googleapis.com/v1beta"
_resolved_model: str | None = None  # model discovered after a 404 (per warm instance)
EXCLUDE = re.compile(r"lite|image|tts|audio|live|embed|vision|learnlm|gemma|aqa|robotics|computer|thinking", re.I)


class _ModelGone(Exception):
    pass


def _headers() -> dict:
    return {"x-goog-api-key": settings.llm.gemini_api_key, "content-type": "application/json"}


def _error(exc: httpx.HTTPStatusError) -> str:
    try:
        detail = exc.response.json().get("error", {}).get("message", "")
    except ValueError:
        detail = ""
    return f"HTTP {exc.response.status_code} {detail[:100]}".strip()


def pick_model(models: list[dict]) -> str | None:
    """Best general Flash model that supports generateContent (stable before preview, newest first)."""
    def version(name: str) -> tuple:
        return tuple(int(x) for x in re.findall(r"\d+", name.split("gemini-", 1)[-1])[:3])

    usable = [m["name"].split("/", 1)[-1] for m in models
              if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [n for n in usable if "flash" in n and n.startswith("gemini") and not EXCLUDE.search(n)]
    if not flash:
        return None
    return sorted(flash, key=lambda n: ("latest" not in n, "preview" in n or "exp" in n, [-v for v in version(n)]))[0]


def discover_model() -> str | None:
    try:
        r = httpx.get(f"{BASE}/models", params={"pageSize": 200}, headers=_headers(), timeout=settings.llm.timeout_s)
        r.raise_for_status()
        return pick_model(r.json().get("models", []))
    except (httpx.HTTPError, ValueError):
        return None


def _generation_config(model: str) -> dict:
    gen = {"temperature": settings.llm.temperature, "maxOutputTokens": max(settings.llm.max_tokens, 1024),
           "responseMimeType": "application/json"}
    if "2.5" in model:
        gen["thinkingConfig"] = {"thinkingBudget": 0}       # 2.5 models: no hidden reasoning for short facts
    elif re.search(r"gemini-[3-9]", model):
        gen["thinkingConfig"] = {"thinkingLevel": "low"}    # newer models: keep reasoning short
    return gen


def _call(model: str, system: str, user: str) -> str:
    try:
        r = httpx.post(
            f"{BASE}/models/{model}:generateContent",
            headers=_headers(),
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": _generation_config(model),
            },
            timeout=settings.llm.timeout_s,
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:  # 429 = free quota used up, 404 = model retired / unknown
        if exc.response.status_code == 404:
            raise _ModelGone(_error(exc)) from exc
        raise LLMUnavailable(_error(exc)) from exc
    except httpx.HTTPError as exc:  # network errors, timeouts
        raise LLMUnavailable(type(exc).__name__) from exc
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, ValueError) as exc:  # e.g. blocked by safety filters
        raise LLMUnavailable("Gemini returned no text") from exc
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise LLMUnavailable("Gemini returned no text")
    return text


def generate(system: str, user: str) -> str:
    global _resolved_model
    if not settings.llm.gemini_api_key:
        raise LLMUnavailable("GEMINI_API_KEY is not set")
    model = _resolved_model or settings.llm.gemini_model
    try:
        return _call(model, system, user)
    except _ModelGone as gone:
        better = discover_model()
        if not better or better == model:
            raise LLMUnavailable(f"model '{model}' unavailable ({gone}); no other Flash model found") from None
        _resolved_model = better
        try:
            return _call(better, system, user)
        except _ModelGone as again:
            raise LLMUnavailable(f"model '{better}' unavailable ({again})") from None


def active_model() -> str:
    return _resolved_model or settings.llm.gemini_model
