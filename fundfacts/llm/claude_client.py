"""Step 4 - Claude (Anthropic Messages API) over httpx. The only LLM provider."""
from __future__ import annotations

import re

import httpx

from fundfacts.config import settings

API_URL = "https://api.anthropic.com/v1/messages"


class LLMUnavailable(RuntimeError):
    """No API key, or the API call failed - the caller falls back to an extractive answer."""


def enabled() -> bool:
    return settings.llm.enabled


def generate(system: str, user: str) -> str:
    if not settings.llm.api_key:
        raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
    try:
        r = httpx.post(
            API_URL,
            headers={"x-api-key": settings.llm.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={
                "model": settings.llm.model,
                "max_tokens": settings.llm.max_tokens,
                "temperature": settings.llm.temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=settings.llm.timeout_s,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"{type(exc).__name__}: {str(exc)[:120]}") from exc
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    return re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.S).strip()
