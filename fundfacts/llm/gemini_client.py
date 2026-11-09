"""Google Gemini (Generative Language API) over httpx.

Free tier: create a key at https://aistudio.google.com/app/apikey (no credit card) and set
GEMINI_API_KEY. Note: on Google's free tier, prompts may be used by Google to improve its
products - FundFacts AI only ever sends the question (after the PII guardrail) and public
document passages.

Model choice: GEMINI_MODEL (default "gemini-flash-lite-latest", Google's alias for the current
Flash-Lite model: fast and the least congested on the free tier, and enough for rewording a
short verified passage). Google retires model names over time; if the configured model answers 404, the client
asks the API which models this key may use, picks the best Flash model and remembers it.
"""
from __future__ import annotations

import re

import httpx

from fundfacts.config import settings
from fundfacts.llm.base import LLMUnavailable

BASE = "https://generativelanguage.googleapis.com/v1beta"
_resolved_model: str | None = None   # last model that answered (per warm instance)
_discovered: list[str] | None = None  # this key's usable Flash models, best first (fetched once)
EXCLUDE = re.compile(r"lite|image|tts|audio|live|embed|vision|learnlm|gemma|aqa|robotics|computer|thinking", re.I)
EXCLUDE_ALT = re.compile(r"image|tts|audio|live|embed|vision|learnlm|gemma|aqa|robotics|computer|thinking", re.I)
ATTEMPT_TIMEOUT_S = 10   # per model; keeps the worst case well under the function's time limit
MAX_ATTEMPTS = 3


class _ModelGone(Exception):
    """404: the model is retired or not available to this key - try another model."""


class _Busy(Exception):
    """503/500/429 or a timeout: the free-tier model is overloaded right now - try another model."""


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


def rank_models(models: list[dict]) -> list[str]:
    """All usable Flash models for failover: Flash-Lite first (fast, least congested), then general Flash."""
    def version(name: str) -> tuple:
        return tuple(int(x) for x in re.findall(r"\d+", name.split("gemini-", 1)[-1])[:3])

    usable = [m["name"].split("/", 1)[-1] for m in models
              if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = [n for n in usable if "flash" in n and n.startswith("gemini") and not EXCLUDE_ALT.search(n)]
    return sorted(flash, key=lambda n: ("lite" not in n, "latest" not in n, "preview" in n or "exp" in n, [-v for v in version(n)]))


def discover_models() -> list[str]:
    global _discovered
    if _discovered is None:
        try:
            r = httpx.get(f"{BASE}/models", params={"pageSize": 200}, headers=_headers(), timeout=ATTEMPT_TIMEOUT_S)
            r.raise_for_status()
            _discovered = rank_models(r.json().get("models", []))
        except (httpx.HTTPError, ValueError):
            return []  # don't cache a failure; try again next time
    return _discovered


def discover_model() -> str | None:
    ranked = [m for m in discover_models() if "lite" not in m]
    return ranked[0] if ranked else None


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
            timeout=min(settings.llm.timeout_s, ATTEMPT_TIMEOUT_S),
        )
        r.raise_for_status()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            raise _ModelGone(_error(exc)) from exc
        if code in (429, 500, 503):  # quota / overloaded: another model may still answer
            raise _Busy(_error(exc)) from exc
        raise LLMUnavailable(_error(exc)) from exc
    except httpx.TimeoutException as exc:
        raise _Busy("timeout") from exc
    except httpx.HTTPError as exc:  # other network errors
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
    """Try the remembered/configured model, then other free Flash models this key can use.

    Failover happens on 404 (retired model), 429/500/503 (quota or overload) and timeouts;
    at most MAX_ATTEMPTS models are tried. The first model that answers is remembered.
    """
    global _resolved_model
    if not settings.llm.gemini_api_key:
        raise LLMUnavailable("GEMINI_API_KEY is not set")
    first = _resolved_model or settings.llm.gemini_model
    tried: list[str] = []
    errors: list[str] = []
    queue = [first]
    while queue and len(tried) < MAX_ATTEMPTS:
        model = queue.pop(0)
        if model in tried:
            continue
        tried.append(model)
        try:
            text = _call(model, system, user)
            _resolved_model = model
            return text
        except (_ModelGone, _Busy) as exc:
            errors.append(f"{model}: {exc}")
            if not queue:  # fetch alternatives only when needed
                queue = [m for m in discover_models() if m not in tried]
    if len(tried) == 1 and errors and not discover_models():
        raise LLMUnavailable(f"{errors[0]}; no other Flash model found")
    raise LLMUnavailable("; ".join(errors)[:200] or "no Gemini model answered")


def active_model() -> str:
    return _resolved_model or settings.llm.gemini_model
